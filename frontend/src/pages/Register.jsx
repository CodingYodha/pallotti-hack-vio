import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { UserPlus, Eye, EyeOff, AlertCircle } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

function Register() {
    const [username, setUsername] = useState('')
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)
    const { register } = useAuth()
    const navigate = useNavigate()

    const handleSubmit = async (e) => {
        e.preventDefault()
        setError('')

        if (password !== confirmPassword) {
            setError('Passwords do not match')
            return
        }

        if (password.length < 6) {
            setError('Password must be at least 6 characters')
            return
        }

        setLoading(true)

        try {
            await register(username, email, password)
            navigate('/dashboard')
        } catch (err) {
            setError(err.response?.data?.detail || 'Registration failed. Please try again.')
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
                    <h1 className="auth-title">Create account</h1>
                    <p className="auth-subtitle">Get started with VioTrack today</p>
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
                            placeholder="Choose a username"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required
                            autoFocus
                        />
                    </div>

                    <div className="auth-field">
                        <label htmlFor="email" className="auth-label">Email</label>
                        <input
                            id="email"
                            type="email"
                            className="auth-input"
                            placeholder="Enter your email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                        />
                    </div>

                    <div className="auth-field">
                        <label htmlFor="password" className="auth-label">Password</label>
                        <div className="auth-input-wrapper">
                            <input
                                id="password"
                                type={showPassword ? 'text' : 'password'}
                                className="auth-input"
                                placeholder="At least 6 characters"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                minLength={6}
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

                    <div className="auth-field">
                        <label htmlFor="confirmPassword" className="auth-label">Confirm Password</label>
                        <input
                            id="confirmPassword"
                            type="password"
                            className="auth-input"
                            placeholder="Repeat your password"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            required
                        />
                    </div>

                    <button
                        type="submit"
                        className="btn btn-primary btn-lg auth-submit"
                        disabled={loading || !username || !email || !password || !confirmPassword}
                    >
                        {loading ? (
                            <span className="auth-spinner"></span>
                        ) : (
                            <>
                                <UserPlus size={18} />
                                Create Account
                            </>
                        )}
                    </button>
                </form>

                <div className="auth-footer">
                    <span>Already have an account?</span>
                    <Link to="/login" className="auth-link">Sign in</Link>
                </div>
            </div>
        </div>
    )
}

export default Register
