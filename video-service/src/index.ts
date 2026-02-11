import { Client } from 'discord.js-selfbot-v13';
import { Streamer, prepareStream, playStream } from '@dank074/discord-video-stream';
import express from 'express';
import { execSync } from 'child_process';
import fs from 'fs';

const app = express();
app.use(express.json());

const BOT_TOKEN = process.env.BOT_TOKEN || '';
const PORT = parseInt(process.env.PORT || '3100');
const VIDEO_WIDTH = parseInt(process.env.VIDEO_WIDTH || '1280');
const VIDEO_HEIGHT = parseInt(process.env.VIDEO_HEIGHT || '720');
const VIDEO_FPS = parseInt(process.env.VIDEO_FPS || '30');
const VIDEO_BITRATE = parseInt(process.env.VIDEO_BITRATE || '2500');
const H26X_PRESET = (process.env.H26X_PRESET || 'ultrafast') as any;

const activeStreams = new Map<string, {
    controller: AbortController;
    title: string;
    url: string;
    startedAt: Date;
}>();

let client: Client;
let streamer: Streamer;

async function initClient(): Promise<void> {
    client = new Client();
    streamer = new Streamer(client);

    await client.login(BOT_TOKEN);
    console.log(`[VIDEO] Logged in as ${client.user?.tag}`);
}

function getDirectUrl(url: string): { videoUrl: string; title: string } {
    try {
        // Use -g to get direct URL, and use cookies to avoid restrictions
        // Use a format that's already merged (has both video and audio)
        const command = `yt-dlp --no-warnings -f "best[height<=?${VIDEO_HEIGHT}][ext=mp4]/bestvideo[height<=?${VIDEO_HEIGHT}][ext=mp4]+bestaudio[ext=m4a]/best" -g --get-title "${url}"`;
        
        console.log(`[VIDEO] Running: ${command}`);
        const output = execSync(command, { 
            timeout: 30000, 
            encoding: 'utf-8',
            maxBuffer: 10 * 1024 * 1024 
        });
        
        const lines = output.trim().split('\n').filter(l => l.trim());
        
        console.log(`[VIDEO] yt-dlp output lines:`, lines);

        if (lines.length >= 2) {
            const title = lines[0];
            const videoUrl = lines[1];
            
            // If we got 3 lines, it means separate video and audio
            if (lines.length === 3) {
                console.log(`[VIDEO] Got separate streams, will need to merge`);
                // For now, just use the video URL and hope it has audio
                // Better solution would be to use FFmpeg to merge both
                return { title, videoUrl };
            }
            
            return { title, videoUrl };
        }
        
        // Fallback: single URL
        return { title: 'Unknown', videoUrl: lines[0] };
    } catch (error: any) {
        console.error(`[VIDEO] yt-dlp error:`, error.message);
        throw new Error(`yt-dlp failed: ${error.message}`);
    }
}

async function startStream(guildId: string, channelId: string, url: string): Promise<{ title: string }> {
    // Stop existing stream if any
    if (activeStreams.has(guildId)) {
        stopStreamForGuild(guildId);
        await new Promise(r => setTimeout(r, 1000));
    }

    // Get direct video URL via yt-dlp
    console.log(`[VIDEO] Resolving URL: ${url}`);
    const { videoUrl, title } = getDirectUrl(url);
    console.log(`[VIDEO] Title: "${title}"`);
    console.log(`[VIDEO] Direct URL: ${videoUrl.substring(0, 100)}...`);
    
    if (!videoUrl || !videoUrl.startsWith('http')) {
        throw new Error(`yt-dlp did not return a valid direct video URL.`);
    }

    // Join voice channel
    await streamer.joinVoice(guildId, channelId);
    await new Promise(r => setTimeout(r, 500));

    // Create stream (Go Live)
    const udpConn = await streamer.createStream();

    const abortController = new AbortController();

    activeStreams.set(guildId, {
        controller: abortController,
        title,
        url,
        startedAt: new Date()
    });

    console.log(`[VIDEO] Starting FFmpeg with direct URL...`);

    try {
        // Use the direct URL from yt-dlp
        // Add extra headers to avoid 403 errors
        const { command, output, promise } = prepareStream(videoUrl, {
            width: VIDEO_WIDTH,
            height: VIDEO_HEIGHT,
            frameRate: VIDEO_FPS,
            bitrateVideo: VIDEO_BITRATE,
            bitrateVideoMax: VIDEO_BITRATE * 1.5,
            bitrateAudio: 128,
            videoCodec: 'H264',
            h26xPreset: H26X_PRESET,
            includeAudio: true,
            hardwareAcceleratedDecoding: false,
            minimizeLatency: true,
            // Add custom FFmpeg flags to handle Google Video URLs
            customFfmpegFlags: [
                '-user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                '-headers', 'Accept: */*',
                '-reconnect', '1',
                '-reconnect_streamed', '1',
                '-reconnect_delay_max', '5'
            ]
        }, abortController.signal);

        // Log FFmpeg command for debugging
        console.log(`[VIDEO] FFmpeg command started`);

        // Handle FFmpeg errors
        command.on('error', (err: any, stdout: any, stderr: any) => {
            console.error(`[VIDEO] FFmpeg error:`, err);
            console.error(`[VIDEO] FFmpeg stderr:`, stderr);
        });

        command.on('start', (commandLine: string) => {
            console.log(`[VIDEO] FFmpeg started: ${commandLine.substring(0, 200)}...`);
        });

        // Play stream in background
        playStream(output, streamer, {
            type: 'go-live',
            width: VIDEO_WIDTH,
            height: VIDEO_HEIGHT,
            frameRate: VIDEO_FPS,
        }, abortController.signal).then(() => {
            console.log(`[VIDEO] Stream finished for guild ${guildId}`);
            cleanupStream(guildId);
        }).catch((err) => {
            if (!abortController.signal.aborted) {
                console.error(`[VIDEO] Stream error for guild ${guildId}:`, err);
            }
            cleanupStream(guildId);
        });

        promise.catch((err) => {
            if (!abortController.signal.aborted) {
                console.error(`[VIDEO] FFmpeg promise error:`, err);
            }
        });

    } catch (error) {
        console.error(`[VIDEO] Failed to start stream:`, error);
        cleanupStream(guildId);
        throw error;
    }

    return { title };
}

function stopStreamForGuild(guildId: string): boolean {
    const stream = activeStreams.get(guildId);
    if (!stream) return false;

    stream.controller.abort();
    cleanupStream(guildId);
    return true;
}

function cleanupStream(guildId: string) {
    activeStreams.delete(guildId);
    try {
        streamer.stopStream();
        streamer.leaveVoice();
    } catch (e) {
        // Ignore cleanup errors
    }
}


app.get('/health', (_req, res) => {
    res.json({ status: 'ok', activeStreams: activeStreams.size });
});

app.post('/stream/start', async (req, res) => {
    const { guild_id, channel_id, url } = req.body;

    if (!guild_id || !channel_id || !url) {
        return res.status(400).json({ error: 'Missing guild_id, channel_id, or url' });
    }

    try {
        const result = await startStream(guild_id, channel_id, url);
        res.json({ success: true, title: result.title });
    } catch (error: any) {
        console.error(`[VIDEO] Start stream error:`, error);
        res.status(500).json({ error: error.message || 'Failed to start stream' });
    }
});

app.post('/stream/stop', (req, res) => {
    const { guild_id } = req.body;

    if (!guild_id) {
        return res.status(400).json({ error: 'Missing guild_id' });
    }

    const stopped = stopStreamForGuild(guild_id);
    res.json({ success: stopped, message: stopped ? 'Stream stopped' : 'No active stream' });
});

app.get('/stream/status', (_req, res) => {
    const streams: Record<string, any> = {};
    for (const [guildId, stream] of activeStreams) {
        streams[guildId] = {
            title: stream.title,
            url: stream.url,
            startedAt: stream.startedAt.toISOString(),
            duration: Math.floor((Date.now() - stream.startedAt.getTime()) / 1000)
        };
    }
    res.json({ active_streams: streams, total: activeStreams.size });
});

app.get('/stream/status/:guild_id', (req, res) => {
    const stream = activeStreams.get(req.params.guild_id);
    if (!stream) {
        return res.json({ active: false });
    }
    res.json({
        active: true,
        title: stream.title,
        url: stream.url,
        startedAt: stream.startedAt.toISOString(),
        duration: Math.floor((Date.now() - stream.startedAt.getTime()) / 1000)
    });
});

// ─── Start ─────────────────────────────────────

async function main() {
    if (!BOT_TOKEN) {
        console.error('[VIDEO] BOT_TOKEN is required');
        process.exit(1);
    }

    try {
        execSync('yt-dlp --version', { encoding: 'utf-8' });
        console.log('[VIDEO] yt-dlp found');
    } catch {
        console.error('[VIDEO] yt-dlp not found! Install it: pip install yt-dlp');
        process.exit(1);
    }

    try {
        execSync('ffmpeg -version', { encoding: 'utf-8', stdio: 'pipe' });
        console.log('[VIDEO] ffmpeg found');
    } catch {
        console.error('[VIDEO] ffmpeg not found! Install it from https://ffmpeg.org');
        process.exit(1);
    }

    await initClient();

    app.listen(PORT, '0.0.0.0', () => {
        console.log(`[VIDEO] API server listening on port ${PORT}`);
        console.log(`[VIDEO] Stream settings: ${VIDEO_WIDTH}x${VIDEO_HEIGHT}@${VIDEO_FPS}fps, ${VIDEO_BITRATE}kbps, preset=${H26X_PRESET}`);
    });
}

main().catch(console.error);