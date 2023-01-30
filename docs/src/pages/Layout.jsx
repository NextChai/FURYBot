import React from 'react'

import { Outlet } from 'react-router-dom'
import { Navbar } from '../components'

const Layout = () => {
    return (
        <div className="bg-gray-dark">

            {/*
            NOTE: Following code is for a BG gradient, but this BG gradient does not take the ENTIRE page
            just the content area. This is not what we want. We want the BG gradient to take the ENTIRE page.
            
                <div className="absolute inset-0 bg-gradient-to-tr from-neutral-900 via-blue-900 to-slate-900 opacity-50" />
                <div className="relative">
                    <Navbar />
                    <Outlet />
                </div>
            */}

            <Navbar />
            <Outlet />
        </div>
    )
}

export default Layout