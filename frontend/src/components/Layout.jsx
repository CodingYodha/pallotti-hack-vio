import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { Sun, Moon, ArrowRight, Languages, LogOut, User } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'
import { useLanguage } from '../context/LanguageContext'
import { useAuth } from '../context/AuthContext'

function Layout() {
    const { theme, toggleTheme } = useTheme()
    const { language, toggleLanguage, t } = useLanguage()
    const { user, isAuthenticated, logout } = useAuth()
    const location = useLocation()
    const navigate = useNavigate()
    const isLandingPage = location.pathname === '/'

    const navItems = [
        { path: '/dashboard', label: t('Dashboard') },
        { path: '/videos', label: t('Videos') },
        { path: '/webcam', label: t('Webcam') },
        { path: '/livestream', label: t('Live Stream') },
        { path: '/search', label: t('Search Violations') },
        { path: '/violations', label: t('Violations') },
        { path: '/employees', label: t('Employees') },
    ]

    const handleLogout = () => {
        logout()
        navigate('/')
    }

    return (
        <div className="app-container">
            {/* Floating Navbar */}
            <nav className="navbar">
                <NavLink to="/" className="navbar-brand">
                    <span className="navbar-brand-text">{t('VioTrack')}</span>
                </NavLink>

                <div className="navbar-nav">
                    {navItems.map((item) => (
                        <NavLink
                            key={item.path}
                            to={item.path}
                            className={({ isActive }) =>
                                `nav-link ${isActive ? 'active' : ''}`
                            }
                        >
                            {item.label}
                        </NavLink>
                    ))}
                </div>

                <div className="navbar-actions">
                    <button
                        className="theme-toggle"
                        onClick={toggleLanguage}
                        aria-label="Switch Language"
                        title={language === 'en' ? 'Switch to Hindi' : 'अंग्रेजी में बदलें'}
                    >
                        <div className="flex items-center gap-1 font-bold text-sm">
                            <Languages size={18} />
                            {language === 'en' ? 'EN' : 'HI'}
                        </div>
                    </button>
                    {!isLandingPage && (
                        <button
                            className="theme-toggle"
                            onClick={toggleTheme}
                            aria-label="Toggle theme"
                        >
                            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
                        </button>
                    )}

                    {isAuthenticated ? (
                        <div className="navbar-user">
                            <span className="navbar-username">
                                <User size={14} />
                                {user?.username}
                            </span>
                            <button
                                className="btn btn-ghost btn-sm"
                                onClick={handleLogout}
                                title="Logout"
                            >
                                <LogOut size={16} />
                                {t('Logout')}
                            </button>
                        </div>
                    ) : (
                        isLandingPage && (
                            <NavLink to="/login" className="btn btn-primary btn-sm">
                                {t('Login')} <ArrowRight size={14} />
                            </NavLink>
                        )
                    )}
                </div>
            </nav>

            {/* Main Content */}
            <main className="main-content">
                <Outlet />
            </main>
        </div>
    )
}

export default Layout
