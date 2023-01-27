import React from 'react'

import { Outlet } from 'react-router-dom'
import { Navbar } from '../components'

const Layout = () => {
    return (
        <div className="bg-gray-dark">
            <div className="absolute inset-0 bg-gradient-to-tr from-neutral-900 via-blue-900 to-slate-900 opacity-50" />
            <div className="relative">
                <Navbar />
                <Outlet />
            </div>
        </div>
    )
}

export default Layout