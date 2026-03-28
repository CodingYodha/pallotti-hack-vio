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
            className="card"
            style={{ minHeight: 400, display: 'flex', flexDirection: 'column', overflow: 'hidden', ...panelStyle }}
        >
            {/* Panel header */}
            <div
                className="card-header"
                style={{ 
                    borderBottom: '1px solid var(--border-color)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '0.5rem',
                    padding: '0.75rem 1rem'
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Activity size={16} style={{ color: 'var(--accent)' }} />
                    <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                        Camera {stream.label || stream.streamId.slice(0, 6).toUpperCase()}
                    </span>
                    {status === 'live' && (
                        <span
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.25rem',
                                fontSize: '0.75rem',
                                fontWeight: 'bold',
                                padding: '0.125rem 0.5rem',
                                borderRadius: '9999px',
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
                        style={{ padding: '0.25rem 0.5rem' }}
                        onClick={() => onRemove(id)}
                        title="Remove this stream"
                    >
                        <Trash2 size={13} />
                    </button>
                )}
            </div>

            {/* Video area */}
            <div
                style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#000', minHeight: 240 }}
            >
                {status === 'idle' && (
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '0.75rem', color: '#555' }}>
                        <WifiOff size={40} style={{ opacity: 0.5 }} />
                        <p style={{ fontSize: '0.875rem' }}>Not connected</p>
                    </div>
                )}
                {status === 'connecting' && (
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '0.75rem', color: 'var(--accent)' }}>
                        <Loader size={36} className="animate-spin" />
                        <p style={{ fontSize: '0.875rem', animation: 'pulse 2s infinite', color: '#fff' }}>Connecting…</p>
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
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '0.75rem', padding: '0 1.5rem', textAlign: 'center' }}>
                        <AlertCircle size={40} style={{ color: 'var(--danger)', opacity: 0.8 }} />
                        <p style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--danger)' }}>Connection Failed</p>
                        <p style={{ fontSize: '0.75rem', color: '#888' }}>
                            Check the URL and ensure the phone is on the same network.
                        </p>
                    </div>
                )}
            </div>

            {/* Controls */}
            <div
                style={{ 
                    borderTop: '1px solid var(--border-color)', 
                    background: 'var(--bg-secondary)',
                    padding: '1rem',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '1rem'
                }}
            >
                {/* URL input */}
                <form onSubmit={handleConnect} style={{ display: 'flex', gap: '0.5rem', width: '100%' }}>
                    <input
                        type="text"
                        value={url}
                        onChange={e => onChange(id, { url: e.target.value })}
                        placeholder="http://ip:port/video  or  rtsp://ip:port/…"
                        className="form-input"
                        style={{ flex: 1, fontSize: '0.85rem', padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-md)' }}
                        disabled={isActive}
                        required
                    />
                    {!isActive ? (
                        <button type="submit" className="btn btn-primary btn-sm" style={{ whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                            <Play size={14} /> Connect
                        </button>
                    ) : (
                        <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            style={{ whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                            onClick={handleDisconnect}
                        >
                            <Square size={14} /> Stop
                        </button>
                    )}
                </form>

                {/* Optional email report */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.85rem' }}>
                        <input
                            type="checkbox"
                            checked={sendEmail}
                            onChange={e => onChange(id, { sendEmail: e.target.checked })}
                            disabled={isActive}
                            style={{ width: '1rem', height: '1rem' }}
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
                            style={{ fontSize: '0.85rem', padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-md)', width: '100%' }}
                        />
                    )}
                </div>
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
            <div className="page-header" style={{ paddingBottom: '1.5rem' }}>
                <div>
                    <h1 className="page-title" style={{ fontSize: '1.875rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <Activity size={30} style={{ color: 'var(--accent)' }} />
                        Multi-Camera Live Stream
                    </h1>
                    <p className="page-description" style={{ marginTop: '0.25rem', color: 'var(--text-secondary)' }}>
                        Connect up to {MAX_STREAMS} phones simultaneously for real-time multi-camera AI analysis.
                    </p>
                </div>

                {/* Action bar */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: '1.5rem', flexWrap: 'wrap' }}>
                    {/* Live indicator */}
                    {liveCount > 0 && (
                        <span
                            style={{
                                display: 'flex', alignItems: 'center', gap: '0.5rem',
                                fontSize: '0.875rem', fontWeight: 'bold',
                                padding: '0.375rem 0.75rem', borderRadius: '9999px',
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
                        className="btn btn-secondary"
                        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
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
                        <button className="btn btn-danger" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }} onClick={stopAll}>
                            <Square size={16} /> Stop All
                        </button>
                    )}
                </div>
            </div>

            {/* How-to tip */}
            <div
                style={{
                    display: 'flex', gap: '0.75rem',
                    padding: '1rem', borderRadius: 'var(--radius-lg)', marginBottom: '1.5rem', fontSize: '0.875rem',
                    background: 'var(--accent-muted)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)'
                }}
            >
                <Info size={18} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: 2 }} />
                <div>
                    <span style={{ fontWeight: 600 }}>Quick setup: </span>
                    Open <strong>IP Webcam</strong> on each Android phone → tap <em>Start server</em> → enter
                    <code style={{ background: 'var(--bg-tertiary)', padding: '2px 6px', borderRadius: '4px', margin: '0 4px', fontSize: '0.8rem', fontFamily: 'monospace' }}>
                        http://&lt;phone-ip&gt;:8080/video
                    </code>
                    in each panel below. All phones must be on the same WiFi.
                </div>
            </div>

            {/* Stream grid */}
            <div style={{ display: 'grid', gridTemplateColumns: gridCols, gap: '1.5rem' }}>
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
