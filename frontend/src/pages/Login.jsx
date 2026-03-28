import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { LogIn, Eye, EyeOff, AlertCircle } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

function Login() {
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)
    const { login } = useAuth()
    const navigate = useNavigate()

    const handleSubmit = async (e) => {
        e.preventDefault()
        setError('')
        setLoading(true)

        try {
            await login(username, password)
            navigate('/dashboard')
        } catch (err) {
            setError(err.response?.data?.detail || 'Invalid credentials. Please try again.')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="auth-page">
            <div className="auth-bg-effects">
                <div className="auth-orb auth-orb-1"></div>
                <div className="auth-orb auth-orb-2"></div>
                <div className="auth-orb auth-orb-3"></div>
            </div>

            <div className="auth-card">
                <div className="auth-card-header">
                    <div className="auth-logo">
                        <span className="auth-logo-text">VioTrack</span>
                    </div>
                    <h1 className="auth-title">Welcome back</h1>
                    <p className="auth-subtitle">Sign in to your account to continue</p>
                </div>

                {error && (
                    <div className="auth-error">
                        <AlertCircle size={16} />
                        <span>{error}</span>
                    </div>
                )}

                <form onSubmit={handleSubmit} className="auth-form">
                    <div className="auth-field">
                        <label htmlFor="username" className="auth-label">Username</label>
                        <input
                            id="username"
                            type="text"
                            className="auth-input"
                            placeholder="Enter your username"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required
                            autoFocus
                        />
                    </div>

                    <div className="auth-field">
                        <label htmlFor="password" className="auth-label">Password</label>
                        <div className="auth-input-wrapper">
                            <input
                                id="password"
                                type={showPassword ? 'text' : 'password'}
                                className="auth-input"
                                placeholder="Enter your password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                            <button
                                type="button"
                                className="auth-input-toggle"
                                onClick={() => setShowPassword(!showPassword)}
                                tabIndex={-1}
                            >
                                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                            </button>
                        </div>
                    </div>

                    <button
                        type="submit"
                        className="btn btn-primary btn-lg auth-submit"
                        disabled={loading || !username || !password}
                    >
                        {loading ? (
                            <span className="auth-spinner"></span>
                        ) : (
                            <>
                                <LogIn size={18} />
                                Sign In
                            </>
                        )}
                    </button>
                </form>

                <div className="auth-footer">
                    <span>Don't have an account?</span>
                    <Link to="/register" className="auth-link">Create account</Link>
                </div>
            </div>
        </div>
    )
}

export default Login
