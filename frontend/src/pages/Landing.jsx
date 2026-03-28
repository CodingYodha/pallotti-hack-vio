import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Shield, Eye, Users, Zap, BarChart3, Video, ChevronRight } from 'lucide-react'
import { useLanguage } from '../context/LanguageContext'
import { useAuth } from '../context/AuthContext'
import DarkVeil from '../components/DarkVeil'
import BorderGlow from '../components/BorderGlow'
import Counter from '../components/Counter'
function Landing() {
    const [currentSlide, setCurrentSlide] = useState(0)
    const { t } = useLanguage()
    const { isAuthenticated } = useAuth()

    // PPE images for carousel
    const slides = [
        {
            id: 1,
            image: '/ppe1.jpg',
            title: t('Real-time Detection'),
            description: t('YOLO-powered detection identifies PPE compliance in real-time')
        },
        {
            id: 2,
            image: '/ppe2.jpg',
            title: t('Individual Tracking'),
            description: t('Deep SORT tracking maintains identity across video frames')
        },
        {
            id: 3,
            image: '/ppe3.jpg',
            title: t('Compliance Reports'),
            description: t('Comprehensive reports for safety audits and compliance')
        }
    ]

    const features = [
        {
            icon: <Shield size={28} />,
            title: t('PPE Detection'),
            description: t('AI detects helmets, vests, gloves, boots using YOLO v8 with 95%+ accuracy'),
            color: 'var(--accent)'
        },
        {
            icon: <Eye size={28} />,
            title: t('Real-time Monitoring'),
            description: t('Live camera feeds processed frame-by-frame for instant violation alerts'),
            color: 'var(--success)'
        },
        {
            icon: <Users size={28} />,
            title: t('Individual Tracking'),
            description: t('Deep SORT maintains persistent identity across video streams'),
            color: 'var(--warning)'
        },
        {
            icon: <BarChart3 size={28} />,
            title: t('Analytics Dashboard'),
            description: t('Comprehensive analytics with violation trends and compliance metrics'),
            color: 'var(--info)'
        },
        {
            icon: <Video size={28} />,
            title: t('Video Processing'),
            description: t('Upload video files for batch processing with detailed frame analysis'),
            color: 'var(--danger)'
        },
        {
            icon: <Zap size={28} />,
            title: t('Instant Alerts'),
            description: t('Email reports and real-time notifications for safety violations'),
            color: '#a78bfa'
        }
    ]

    const stats = [
        { value: 95, suffix: '%+', label: t('Detection Accuracy') },
        { value: 30, suffix: 'fps', label: t('Processing Speed') },
        { value: 5, suffix: '+', label: t('PPE Categories') },
        { value: 24, suffix: '/7', label: t('Monitoring') },
    ]

    useEffect(() => {
        const timer = setInterval(() => {
            setCurrentSlide((prev) => (prev + 1) % slides.length)
        }, 4000)
        return () => clearInterval(timer)
    }, [slides.length])

    return (
        <div className="landing" style={{ backgroundImage: 'none', backgroundColor: 'transparent' }}>
            <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100vh', zIndex: -1 }}>
                <DarkVeil />
            </div>

            {/* Hero Section */}
            <section className="landing-hero">
                <div className="landing-hero-bg">
                </div>

                <div className="landing-hero-content">
                    <div className="landing-hero-text">
                        <div className="hero-badge">
                            <span className="hero-badge-dot"></span>
                            AI-Powered Safety Analytics
                        </div>

                        <h1 className="landing-hero-title">
                            {t('Safety compliance,')}
                            <br />
                            <span className="landing-hero-title-accent">{t('reimagined')}</span>
                        </h1>

                        <p className="landing-hero-description">
                            {t('Automatically detect PPE violations, track individuals across video feeds, and generate actionable compliance reports — all powered by advanced computer vision.')}
                        </p>

                        <div className="landing-hero-cta">
                            {isAuthenticated ? (
                                <Link to="/dashboard" className="btn btn-primary btn-lg">
                                    {t('Open Dashboard')} <ArrowRight size={18} />
                                </Link>
                            ) : (
                                <Link to="/register" className="btn btn-primary btn-lg">
                                    {t('Get Started')} <ArrowRight size={18} />
                                </Link>
                            )}
                            <Link to={isAuthenticated ? "/videos" : "/login"} className="btn btn-secondary btn-lg">
                                {isAuthenticated ? t('Upload Video') : t('Sign In')}
                            </Link>
                        </div>
                    </div>

                    {/* Carousel */}
                    <div className="landing-carousel">
                        {slides.map((slide, index) => (
                            <div
                                key={slide.id}
                                className={`landing-carousel-slide ${index === currentSlide ? 'active' : ''}`}
                            >
                                <img
                                    src={slide.image}
                                    alt={slide.title}
                                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                />
                                <div className="landing-carousel-caption">
                                    <h3>{slide.title}</h3>
                                    <p>{slide.description}</p>
                                </div>
                            </div>
                        ))}
                        <div className="landing-carousel-dots">
                            {slides.map((_, index) => (
                                <button
                                    key={index}
                                    className={`landing-carousel-dot ${index === currentSlide ? 'active' : ''}`}
                                    onClick={() => setCurrentSlide(index)}
                                    aria-label={`Go to slide ${index + 1}`}
                                />
                            ))}
                        </div>
                    </div>
                </div>
            </section>

            {/* Stats Bar */}
            <section className="landing-stats">
                <div className="landing-stats-inner">
                    {stats.map((stat, i) => (
                        <div key={i} className="landing-stat">
                            <span className="landing-stat-value" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                <Counter value={stat.value} fontSize={32} />
                                {stat.suffix}
                            </span>
                            <span className="landing-stat-label">{stat.label}</span>
                        </div>
                    ))}
                </div>
            </section>

            {/* Features Grid */}
            <section className="landing-features">
                <div className="landing-section-header">
                    <h2 className="landing-section-title">{t('Everything you need for safety compliance')}</h2>
                    <p className="landing-section-subtitle">
                        {t('Advanced AI capabilities designed for industrial safety monitoring')}
                    </p>
                </div>
                <div className="landing-features-grid">
                    {features.map((feature, i) => (
                        <BorderGlow key={i} className="landing-feature-card" backgroundColor="var(--bg-surface)" animated={false}>
                            <div className="landing-feature-icon" style={{ color: feature.color, background: `${feature.color}15` }}>
                                {feature.icon}
                            </div>
                            <h3 className="landing-feature-title">{feature.title}</h3>
                            <p className="landing-feature-desc">{feature.description}</p>
                        </BorderGlow>
                    ))}
                </div>
            </section>

            {/* CTA Section */}
            <section className="landing-cta">
                <div className="landing-cta-content">
                    <h2 className="landing-cta-title">{t('Ready to enhance your safety compliance?')}</h2>
                    <p className="landing-cta-desc">
                        {t('Get started today and see the power of AI-driven violation detection.')}
                    </p>
                    <Link
                        to={isAuthenticated ? "/dashboard" : "/register"}
                        className="btn btn-primary btn-lg"
                    >
                        {isAuthenticated ? t('Go to Dashboard') : t('Create Free Account')}
                        <ChevronRight size={18} />
                    </Link>
                </div>
            </section>
        </div>
    )
}

export default Landing
