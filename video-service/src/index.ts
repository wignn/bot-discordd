import { Client } from 'discord.js-selfbot-v13';
import { Streamer, prepareStream, playStream } from '@dank074/discord-video-stream';
import express from 'express';
import { execSync } from 'child_process';

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

function getYtDlpUrl(url: string): { videoUrl: string; title: string } {
    try {

        const output = execSync(
            `yt-dlp --no-warnings -f "best[height<=?${VIDEO_HEIGHT}]/bestvideo[height<=?${VIDEO_HEIGHT}]+bestaudio/best" --merge-output-format mp4 --get-url --get-title "${url}"`,
            { timeout: 30000, encoding: 'utf-8' }
        );
        const lines = output.trim().split('\n').filter(l => l.trim());

        if (lines.length >= 2) {
            return { title: lines[0], videoUrl: lines[1] };
        }
        return { title: 'Unknown', videoUrl: lines[0] };
    } catch (error) {
        throw new Error(`yt-dlp failed: ${error}`);
    }
}

async function startStream(guildId: string, channelId: string, url: string): Promise<{ title: string }> {

    if (activeStreams.has(guildId)) {
        stopStreamForGuild(guildId);
        await new Promise(r => setTimeout(r, 1000));
    }


    console.log(`[VIDEO] Resolving URL: ${url}`);
    const { videoUrl, title } = getYtDlpUrl(url);
    console.log(`[VIDEO] yt-dlp result: title="${title}", videoUrl="${videoUrl}"`);
    if (!videoUrl || !videoUrl.startsWith('http')) {
        throw new Error(`yt-dlp did not return a valid direct video URL. Cek apakah video dibatasi, private, atau yt-dlp perlu update.`);
    }
    console.log(`[VIDEO] Playing: ${title}`);

    await streamer.joinVoice(guildId, channelId);
    await new Promise(r => setTimeout(r, 500));

    const udpConn = await streamer.createStream();

    const abortController = new AbortController();

    activeStreams.set(guildId, {
        controller: abortController,
        title,
        url,
        startedAt: new Date()
    });

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