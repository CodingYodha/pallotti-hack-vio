import React, { useState, useRef, useCallback } from 'react';
import {
    Play, Square, Loader, AlertCircle, Info, Activity,
    Plus, Trash2, Wifi, WifiOff
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const MAX_STREAMS = 4;

// Generate a short human-readable ID
const genId = () => Math.random().toString(36).slice(2, 8);

const makeStream = () => ({
    id: genId(),          // unique frontend key
    streamId: genId(),    // passed to backend as stream_id
    url: '',
    sendEmail: false,
    email: '',
    status: 'idle',       // idle | connecting | live | error
    src: '',
});

// ─── per-stream panel ────────────────────────────────────────────────────────

function StreamPanel({ stream, onChange, onRemove, totalStreams }) {
    const imgRef = useRef(null);
    const { id, url, sendEmail, email, status } = stream;

    const isActive = status === 'live' || status === 'connecting';

    const handleConnect = (e) => {
        e.preventDefault();
        if (!url.trim()) return;

        onChange(id, { status: 'connecting' });

        setTimeout(() => {
            let endpoint = `${API_BASE}/api/stream/live?rtsp_url=${encodeURIComponent(url)}&stream_id=${stream.streamId}`;
            if (sendEmail && email) {
                endpoint += `&send_email=true&mail_to=${encodeURIComponent(email)}`;
            }
            onChange(id, { status: 'live', src: endpoint });
        }, 500);
    };

    const handleDisconnect = async () => {
        try {
            await fetch(`${API_BASE}/api/stream/stop?stream_id=${stream.streamId}`, { method: 'POST' });
        } catch (_) {}
        onChange(id, { status: 'idle', src: '' });
    };

    // Column span for single stream — give it full width
    const panelStyle = totalStreams === 1
        ? { gridColumn: '1 / -1' }
        : {};

    return (
        <div
            className="card overflow-hidden flex flex-col"
            style={{ minHeight: 380, ...panelStyle }}
        >
            {/* Panel header */}
            <div
                className="card-header flex items-center justify-between gap-2 py-3 px-4"
                style={{ borderBottom: '1px solid var(--border-color)' }}
            >
                <div className="flex items-center gap-2">
                    <Activity size={16} style={{ color: 'var(--accent)' }} />
                    <span className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
                        Camera {stream.label || stream.streamId.slice(0, 6).toUpperCase()}
                    </span>
                    {status === 'live' && (
                        <span
                            className="flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full"
                            style={{
                                background: 'rgba(239,68,68,0.12)',
                                color: '#ef4444',
                                border: '1px solid rgba(239,68,68,0.25)'
                            }}
                        >
                            <span
                                style={{
                                    width: 6, height: 6, borderRadius: '50%',
                                    background: '#ef4444',
                                    animation: 'pulse 1.5s ease-in-out infinite'
                                }}
                            />
                            LIVE
                        </span>
                    )}
                </div>
                {/* Remove button — only when idle and there's more than 1 stream */}
                {!isActive && totalStreams > 1 && (
                    <button
                        className="btn btn-danger btn-sm"
                        style={{ padding: '4px 8px' }}
                        onClick={() => onRemove(id)}
                        title="Remove this stream"
                    >
                        <Trash2 size={13} />
                    </button>
                )}
            </div>

            {/* Video area */}
            <div
                className="flex-1 flex flex-col"
                style={{ background: '#000', minHeight: 240 }}
            >
                {status === 'idle' && (
                    <div className="flex-1 flex flex-col items-center justify-center gap-3" style={{ color: '#555' }}>
                        <WifiOff size={40} style={{ opacity: 0.5 }} />
                        <p className="text-sm">Not connected</p>
                    </div>
                )}
                {status === 'connecting' && (
                    <div className="flex-1 flex flex-col items-center justify-center gap-3" style={{ color: 'var(--accent)' }}>
                        <Loader size={36} className="animate-spin" />
                        <p className="text-sm animate-pulse" style={{ color: '#fff' }}>Connecting…</p>
                    </div>
                )}
                {status === 'live' && (
                    <img
                        ref={imgRef}
                        src={stream.src}
                        alt="Live stream"
                        style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }}
                        onError={() => onChange(id, { status: 'error', src: '' })}
                    />
                )}
                {status === 'error' && (
                    <div className="flex-1 flex flex-col items-center justify-center gap-3 px-6 text-center">
                        <AlertCircle size={40} style={{ color: 'var(--danger)', opacity: 0.8 }} />
                        <p className="font-semibold text-sm" style={{ color: 'var(--danger)' }}>Connection Failed</p>
                        <p className="text-xs" style={{ color: '#888' }}>
                            Check the URL and ensure the phone is on the same network.
                        </p>
                    </div>
                )}
            </div>

            {/* Controls */}
            <div
                className="px-4 py-3 flex flex-col gap-2"
                style={{ borderTop: '1px solid var(--border-color)', background: 'var(--bg-secondary)' }}
            >
                {/* URL input */}
                <form onSubmit={handleConnect} className="flex gap-2">
                    <input
                        type="text"
                        value={url}
                        onChange={e => onChange(id, { url: e.target.value })}
                        placeholder="http://ip:port/video  or  rtsp://ip:port/…"
                        className="form-input flex-1"
                        style={{ fontSize: '0.8rem', padding: '6px 10px' }}
                        disabled={isActive}
                        required
                    />
                    {!isActive ? (
                        <button type="submit" className="btn btn-primary btn-sm" style={{ whiteSpace: 'nowrap' }}>
                            <Play size={13} /> Connect
                        </button>
                    ) : (
                        <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            style={{ whiteSpace: 'nowrap' }}
                            onClick={handleDisconnect}
                        >
                            <Square size={13} /> Stop
                        </button>
                    )}
                </form>

                {/* Optional email report */}
                <label className="flex items-center gap-2 cursor-pointer" style={{ fontSize: '0.78rem' }}>
                    <input
                        type="checkbox"
                        checked={sendEmail}
                        onChange={e => onChange(id, { sendEmail: e.target.checked })}
                        disabled={isActive}
                        className="w-3.5 h-3.5"
                    />
                    <span style={{ color: 'var(--text-secondary)' }}>Email report on stop</span>
                </label>
                {sendEmail && !isActive && (
                    <input
                        type="email"
                        value={email}
                        onChange={e => onChange(id, { email: e.target.value })}
                        placeholder="manager@example.com"
                        className="form-input"
                        style={{ fontSize: '0.78rem', padding: '5px 10px' }}
                    />
                )}
            </div>
        </div>
    );
}

// ─── main page ───────────────────────────────────────────────────────────────

function LiveStream() {
    const [streams, setStreams] = useState([makeStream()]);

    const updateStream = useCallback((id, patch) => {
        setStreams(prev => prev.map(s => s.id === id ? { ...s, ...patch } : s));
    }, []);

    const addStream = () => {
        if (streams.length >= MAX_STREAMS) return;
        setStreams(prev => [...prev, makeStream()]);
    };

    const removeStream = (id) => {
        setStreams(prev => prev.filter(s => s.id !== id));
    };

    const stopAll = async () => {
        try {
            await fetch(`${API_BASE}/api/stream/stop`, { method: 'POST' });
        } catch (_) {}
        setStreams(prev => prev.map(s => ({ ...s, status: 'idle', src: '' })));
    };

    const liveCount = streams.filter(s => s.status === 'live').length;

    // Adaptive grid: 1 stream = 1 col, 2+ = 2 cols
    const gridCols = streams.length === 1 ? '1fr' : 'repeat(2, 1fr)';

    return (
        <div className="page-container">
            {/* Page header */}
            <div className="page-header pb-4">
                <div>
                    <h1 className="page-title text-3xl font-bold flex items-center gap-3">
                        <Activity size={30} style={{ color: 'var(--accent)' }} />
                        Multi-Camera Live Stream
                    </h1>
                    <p className="page-description mt-1" style={{ color: 'var(--text-secondary)' }}>
                        Connect up to {MAX_STREAMS} phones simultaneously for real-time multi-camera AI analysis.
                    </p>
                </div>

                {/* Action bar */}
                <div className="flex items-center gap-3 mt-4 flex-wrap">
                    {/* Live indicator */}
                    {liveCount > 0 && (
                        <span
                            className="flex items-center gap-2 text-sm font-bold px-3 py-1.5 rounded-full"
                            style={{
                                background: 'rgba(239,68,68,0.12)',
                                color: '#ef4444',
                                border: '1px solid rgba(239,68,68,0.3)'
                            }}
                        >
                            <Wifi size={14} />
                            {liveCount} stream{liveCount > 1 ? 's' : ''} live
                        </span>
                    )}

                    {/* Add stream */}
                    <button
                        className="btn btn-secondary flex items-center gap-2"
                        onClick={addStream}
                        disabled={streams.length >= MAX_STREAMS}
                        title={streams.length >= MAX_STREAMS ? `Max ${MAX_STREAMS} streams` : 'Add another stream'}
                    >
                        <Plus size={16} />
                        Add Stream
                        <span
                            className="badge"
                            style={{
                                background: 'var(--bg-tertiary)',
                                color: 'var(--text-secondary)',
                                fontSize: '0.7rem',
                                padding: '1px 6px',
                                borderRadius: 99
                            }}
                        >
                            {streams.length}/{MAX_STREAMS}
                        </span>
                    </button>

                    {/* Stop all */}
                    {liveCount > 0 && (
                        <button className="btn btn-danger flex items-center gap-2" onClick={stopAll}>
                            <Square size={16} /> Stop All
                        </button>
                    )}
                </div>
            </div>

            {/* How-to tip */}
            <div
                className="flex gap-3 p-4 rounded-lg mb-6 text-sm"
                style={{
                    background: 'var(--accent-muted)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)'
                }}
            >
                <Info size={18} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: 2 }} />
                <div>
                    <span className="font-semibold">Quick setup: </span>
                    Open <strong>IP Webcam</strong> on each Android phone → tap <em>Start server</em> → enter
                    <code style={{ background: 'var(--bg-tertiary)', padding: '1px 6px', borderRadius: 4, margin: '0 4px' }}>
                        http://&lt;phone-ip&gt;:8080/video
                    </code>
                    in each panel below. All phones must be on the same WiFi.
                </div>
            </div>

            {/* Stream grid */}
            <div style={{ display: 'grid', gridTemplateColumns: gridCols, gap: '1.25rem' }}>
                {streams.map(stream => (
                    <StreamPanel
                        key={stream.id}
                        stream={stream}
                        onChange={updateStream}
                        onRemove={removeStream}
                        totalStreams={streams.length}
                    />
                ))}
            </div>
        </div>
    );
}

export default LiveStream;
