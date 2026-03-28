import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider } from './context/ThemeContext'
import { LanguageProvider } from './context/LanguageContext'
import { AuthProvider, useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Videos from './pages/Videos'
import Violations from './pages/Violations'
import Individuals from './pages/Individuals'
import VideoDetail from './pages/VideoDetail'
import Webcam from './pages/Webcam'
import LiveStream from './pages/LiveStream'
import SearchViolations from './pages/SearchViolations'
import Employees from './pages/Employees'

function ProtectedRoute({ children }) {
    const { isAuthenticated, loading } = useAuth()

    if (loading) {
        return (
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '100vh',
                color: 'var(--text-muted)',
                fontSize: '1rem'
            }}>
                Loading...
            </div>
        )
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />
    }

    return children
}

function AppRoutes() {
    return (
        <Routes>
            {/* Public routes — no layout */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />

            {/* Routes with layout */}
            <Route path="/" element={<Layout />}>
                <Route index element={<Landing />} />
                <Route path="dashboard" element={
                    <ProtectedRoute><Dashboard /></ProtectedRoute>
                } />
                <Route path="videos" element={
                    <ProtectedRoute><Videos /></ProtectedRoute>
                } />
                <Route path="videos/:videoId" element={
                    <ProtectedRoute><VideoDetail /></ProtectedRoute>
                } />
                <Route path="violations" element={
                    <ProtectedRoute><Violations /></ProtectedRoute>
                } />
                <Route path="webcam" element={
                    <ProtectedRoute><Webcam /></ProtectedRoute>
                } />
                <Route path="livestream" element={
                    <ProtectedRoute><LiveStream /></ProtectedRoute>
                } />
                <Route path="search" element={
                    <ProtectedRoute><SearchViolations /></ProtectedRoute>
                } />
                <Route path="individuals/:videoId" element={
                    <ProtectedRoute><Individuals /></ProtectedRoute>
                } />
                <Route path="employees" element={
                    <ProtectedRoute><Employees /></ProtectedRoute>
                } />
            </Route>
        </Routes>
    )
}

function App() {
    return (
        <LanguageProvider>
            <ThemeProvider>
                <AuthProvider>
                    <BrowserRouter>
                        <AppRoutes />
                    </BrowserRouter>
                </AuthProvider>
            </ThemeProvider>
        </LanguageProvider>
    )
}

export default App
