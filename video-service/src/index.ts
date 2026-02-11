import { Client } from 'discord.js-selfbot-v13';
import { Streamer, prepareStream, playStream } from '@dank074/discord-video-stream';
import express from 'express';
import { execSync, spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

const app = express();
app.use(express.json());

const BOT_TOKEN = process.env.BOT_TOKEN || '';
const PORT = parseInt(process.env.PORT || '3100');
const VIDEO_WIDTH = parseInt(process.env.VIDEO_WIDTH || '1280');
const VIDEO_HEIGHT = parseInt(process.env.VIDEO_HEIGHT || '720');
const VIDEO_FPS = parseInt(process.env.VIDEO_FPS || '30');
const VIDEO_BITRATE = parseInt(process.env.VIDEO_BITRATE || '2500');
const H26X_PRESET = (process.env.H26X_PRESET || 'ultrafast') as any;
const TEMP_DIR = process.env.TEMP_DIR || '/tmp/videos';

// Ensure temp directory exists
if (!fs.existsSync(TEMP_DIR)) {
    fs.mkdirSync(TEMP_DIR, { recursive: true });
}

const activeStreams = new Map<string, {
    controller: AbortController;
    title: string;
    url: string;
    startedAt: Date;
    videoPath?: string;
}>();

let client: Client;
let streamer: Streamer;

async function initClient(): Promise<void> {
    client = new Client();
    streamer = new Streamer(client);

    await client.login(BOT_TOKEN);
    console.log(`[VIDEO] Logged in as ${client.user?.tag}`);
}

function downloadVideo(url: string): Promise<{ videoPath: string; title: string }> {
    return new Promise((resolve, reject) => {
        try {
            // Get title first
            console.log(`[VIDEO] Fetching video title...`);
            const titleOutput = execSync(
                `yt-dlp --no-warnings --get-title "${url}"`,
                { timeout: 10000, encoding: 'utf-8' }
            );
            const title = titleOutput.trim();
            console.log(`[VIDEO] Title: ${title}`);

            // Generate safe filename
            const timestamp = Date.now();
            const safeTitle = title.replace(/[^a-z0-9]/gi, '_').substring(0, 50);
            const videoPath = path.join(TEMP_DIR, `${timestamp}_${safeTitle}.mp4`);

            console.log(`[VIDEO] Downloading video to ${videoPath}...`);
            
            // Download video with progress
            const ytdlp = spawn('yt-dlp', [
                '--no-warnings',
                '-f', `bestvideo[height<=?${VIDEO_HEIGHT}]+bestaudio/best[height<=?${VIDEO_HEIGHT}]`,
                '--merge-output-format', 'mp4',
                '-o', videoPath,
                url
            ]);

            let downloadProgress = '';

            ytdlp.stdout.on('data', (data) => {
                downloadProgress = data.toString();
                // Extract percentage if available
                const match = downloadProgress.match(/(\d+\.\d+)%/);
                if (match) {
                    process.stdout.write(`\r[VIDEO] Download progress: ${match[1]}%`);
                }
            });

            ytdlp.stderr.on('data', (data) => {
                const output = data.toString();
                // Show download progress from stderr as well
                const match = output.match(/(\d+\.\d+)%/);
                if (match) {
                    process.stdout.write(`\r[VIDEO] Download progress: ${match[1]}%`);
                }
            });

            ytdlp.on('close', (code) => {
                console.log(''); // New line after progress
                if (code === 0) {
                    console.log(`[VIDEO] Download complete: ${videoPath}`);
                    resolve({ videoPath, title });
                } else {
                    reject(new Error(`yt-dlp download failed with code ${code}`));
                }
            });

            ytdlp.on('error', (error) => {
                reject(new Error(`yt-dlp process error: ${error.message}`));
            });

        } catch (error: any) {
            reject(new Error(`Download failed: ${error.message}`));
        }
    });
}

async function startStream(guildId: string, channelId: string, url: string): Promise<{ title: string }> {
    // Stop existing stream if any
    if (activeStreams.has(guildId)) {
        await stopStreamForGuild(guildId);
        await new Promise(r => setTimeout(r, 1000));
    }

    // Download video first
    console.log(`[VIDEO] Starting download for: ${url}`);
    const { videoPath, title } = await downloadVideo(url);
    
    console.log(`[VIDEO] Playing: ${title}`);

    await streamer.joinVoice(guildId, channelId);
    await new Promise(r => setTimeout(r, 500));

    const udpConn = await streamer.createStream();

    const abortController = new AbortController();

    activeStreams.set(guildId, {
        controller: abortController,
        title,
        url,
        startedAt: new Date(),
        videoPath
    });

    // Prepare FFmpeg stream from local file
    const { command, output, promise } = prepareStream(videoPath, {
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
    }, abortController.signal);

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
            console.error(`[VIDEO] FFmpeg error:`, err);
        }
    });

    return { title };
}

async function stopStreamForGuild(guildId: string): Promise<boolean> {
    const stream = activeStreams.get(guildId);
    if (!stream) return false;

    stream.controller.abort();
    await cleanupStream(guildId);
    return true;
}

async function cleanupStream(guildId: string) {
    const stream = activeStreams.get(guildId);
    
    // Delete downloaded video file if exists
    if (stream?.videoPath && fs.existsSync(stream.videoPath)) {
        try {
            fs.unlinkSync(stream.videoPath);
            console.log(`[VIDEO] Deleted temp file: ${stream.videoPath}`);
        } catch (e) {
            console.error(`[VIDEO] Failed to delete temp file: ${e}`);
        }
    }

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

app.post('/stream/stop', async (req, res) => {
    const { guild_id } = req.body;

    if (!guild_id) {
        return res.status(400).json({ error: 'Missing guild_id' });
    }

    const stopped = await stopStreamForGuild(guild_id);
    res.json({ success: stopped, message: stopped ? 'Stream stopped' : 'No active stream' });
});

app.get('/stream/status', (_req, res) => {
    const streams: Record<string, any> = {};
    for (const [guildId, stream] of activeStreams) {
        streams[guildId] = {
            title: stream.title,
            url: stream.url,
            startedAt: stream.startedAt.toISOString(),
            duration: Math.floor((Date.now() - stream.startedAt.getTime()) / 1000),
            hasLocalFile: !!stream.videoPath
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
        duration: Math.floor((Date.now() - stream.startedAt.getTime()) / 1000),
        hasLocalFile: !!stream.videoPath
    });
});

// Cleanup old temp files on startup
app.get('/cleanup', (_req, res) => {
    try {
        const files = fs.readdirSync(TEMP_DIR);
        let deleted = 0;
        
        for (const file of files) {
            const filePath = path.join(TEMP_DIR, file);
            const stats = fs.statSync(filePath);
            const ageHours = (Date.now() - stats.mtimeMs) / (1000 * 60 * 60);
            
            // Delete files older than 2 hours
            if (ageHours > 2) {
                fs.unlinkSync(filePath);
                deleted++;
            }
        }
        
        res.json({ success: true, deleted });
    } catch (error: any) {
        res.status(500).json({ error: error.message });
    }
});


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

    try {
        const files = fs.readdirSync(TEMP_DIR);
        for (const file of files) {
            const filePath = path.join(TEMP_DIR, file);
            try {
                fs.unlinkSync(filePath);
            } catch (e) {
                // Ignore errors
            }
        }
        console.log('[VIDEO] Cleaned up temp directory');
    } catch (e) {
        console.log('[VIDEO] No temp files to clean up');
    }

    await initClient();

    app.listen(PORT, '0.0.0.0', () => {
        console.log(`[VIDEO] API server listening on port ${PORT}`);
        console.log(`[VIDEO] Stream settings: ${VIDEO_WIDTH}x${VIDEO_HEIGHT}@${VIDEO_FPS}fps, ${VIDEO_BITRATE}kbps, preset=${H26X_PRESET}`);
        console.log(`[VIDEO] Temp directory: ${TEMP_DIR}`);
    });
}

main().catch(console.error);