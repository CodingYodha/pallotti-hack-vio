import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { loginUser, registerUser, getCurrentUser } from '../services/api'

const AuthContext = createContext()

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null)
    const [token, setToken] = useState(() => localStorage.getItem('viotrack-token'))
    const [loading, setLoading] = useState(true)

    // On mount, validate stored token
    useEffect(() => {
        const validateToken = async () => {
            if (token) {
                try {
                    const response = await getCurrentUser(token)
                    setUser(response.data)
                } catch {
                    // Token invalid/expired
                    localStorage.removeItem('viotrack-token')
                    setToken(null)
                    setUser(null)
                }
            }
            setLoading(false)
        }
        validateToken()
    }, [])

    const login = useCallback(async (username, password) => {
        const response = await loginUser({ username, password })
        const { access_token, user: userData } = response.data
        localStorage.setItem('viotrack-token', access_token)
        setToken(access_token)
        setUser(userData)
        return userData
    }, [])

    const register = useCallback(async (username, email, password) => {
        const response = await registerUser({ username, email, password })
        const { access_token, user: userData } = response.data
        localStorage.setItem('viotrack-token', access_token)
        setToken(access_token)
        setUser(userData)
        return userData
    }, [])

    const logout = useCallback(() => {
        localStorage.removeItem('viotrack-token')
        setToken(null)
        setUser(null)
    }, [])

    return (
        <AuthContext.Provider value={{
            user,
            token,
            loading,
            login,
            register,
            logout,
            isAuthenticated: !!user,
        }}>
            {children}
        </AuthContext.Provider>
    )
}

export function useAuth() {
    const context = useContext(AuthContext)
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider')
    }
    return context
}
