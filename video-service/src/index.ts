import { Client } from 'discord.js-selfbot-v13';
import { Streamer, prepareStream, playStream } from '@dank074/discord-video-stream';
import express from 'express';
import { execSync, spawn } from 'child_process';
import { Readable } from 'stream';

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
    ytdlpProcess?: any;
}>();

let client: Client;
let streamer: Streamer;

async function initClient(): Promise<void> {
    client = new Client();
    streamer = new Streamer(client);

    await client.login(BOT_TOKEN);
    console.log(`[VIDEO] Logged in as ${client.user?.tag}`);
}

function getVideoTitle(url: string): string {
    try {
        const output = execSync(
            `yt-dlp --no-warnings --get-title "${url}"`,
            { timeout: 10000, encoding: 'utf-8' }
        );
        return output.trim() || 'Unknown';
    } catch (error) {
        console.error(`[VIDEO] Failed to get title, using default`);
        return 'Unknown Video';
    }
}

async function startStream(guildId: string, channelId: string, url: string): Promise<{ title: string }> {

    if (activeStreams.has(guildId)) {
        await stopStreamForGuild(guildId);
        await new Promise(r => setTimeout(r, 1000));
    }
    console.log(`[VIDEO] Fetching title for: ${url}`);
    const title = getVideoTitle(url);
    console.log(`[VIDEO] Playing: ${title}`);

    await streamer.joinVoice(guildId, channelId);
    await new Promise(r => setTimeout(r, 500));

    const udpConn = await streamer.createStream();

    const abortController = new AbortController();

    console.log(`[VIDEO] Starting yt-dlp process...`);
    const ytdlpProcess = spawn('yt-dlp', [
        '--no-warnings',
        '--format', `bestvideo[height<=?${VIDEO_HEIGHT}]+bestaudio/best[height<=?${VIDEO_HEIGHT}]`,
        '--output', '-', 
        '--quiet',
        '--no-playlist',
        url
    ], {
        stdio: ['ignore', 'pipe', 'pipe']
    });

    activeStreams.set(guildId, {
        controller: abortController,
        title,
        url,
        startedAt: new Date(),
        ytdlpProcess
    });

    ytdlpProcess.stderr.on('data', (data: Buffer) => {
        const msg = data.toString();
        if (msg.includes('ERROR') || msg.includes('WARNING')) {
            console.error(`[VIDEO] yt-dlp: ${msg}`);
        }
    });

    ytdlpProcess.on('error', (error: Error) => {
        console.error(`[VIDEO] yt-dlp process error:`, error);
        cleanupStream(guildId);
    });

    console.log(`[VIDEO] Preparing FFmpeg stream...`);
    
    const inputStream = ytdlpProcess.stdout;

    try {
        const { command, output, promise } = prepareStream(inputStream, {
            width: VIDEO_WIDTH,
            height: VIDEO_HEIGHT,
            frameRate: VIDEO_FPS,
            bitrateVideo: VIDEO_BITRATE,
            bitrateVideoMax: Math.floor(VIDEO_BITRATE * 1.5),
            bitrateAudio: 128,
            videoCodec: 'H264',
            h26xPreset: H26X_PRESET,
            includeAudio: true,
            hardwareAcceleratedDecoding: false,
            minimizeLatency: true,
        }, abortController.signal);

        console.log(`[VIDEO] Starting playback...`);

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

    } catch (error) {
        console.error(`[VIDEO] Failed to prepare stream:`, error);
        ytdlpProcess.kill();
        cleanupStream(guildId);
        throw error;
    }

    return { title };
}

async function stopStreamForGuild(guildId: string): Promise<boolean> {
    const stream = activeStreams.get(guildId);
    if (!stream) return false;

    console.log(`[VIDEO] Stopping stream for guild ${guildId}`);
    
    if (stream.ytdlpProcess) {
        try {
            stream.ytdlpProcess.kill('SIGTERM');
            setTimeout(() => {
                if (stream.ytdlpProcess && !stream.ytdlpProcess.killed) {
                    stream.ytdlpProcess.kill('SIGKILL');
                }
            }, 2000);
        } catch (e) {
            console.error(`[VIDEO] Error killing yt-dlp process:`, e);
        }
    }

    stream.controller.abort();
    cleanupStream(guildId);
    return true;
}

function cleanupStream(guildId: string) {
    const stream = activeStreams.get(guildId);
    
    if (stream?.ytdlpProcess) {
        try {
            stream.ytdlpProcess.kill();
        } catch (e) {
            // Ignore
        }
    }

    activeStreams.delete(guildId);
    
    try {
        streamer.stopStream();
        streamer.leaveVoice();
    } catch (e) {
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
        console.log(`[VIDEO] Using direct pipe from yt-dlp (no download, no expired URLs)`);
    });
}

main().catch(console.error);