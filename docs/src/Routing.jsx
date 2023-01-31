import React from 'react';
import { Routes, Route, BrowserRouter } from "react-router-dom";
import { Docs, Home, Layout } from './pages';

const basename = process.env.NODE_ENV === 'production' ? '/Fury-Bot' : '/';

const Routing = () => {
  return (
    <div>
      <BrowserRouter basename={basename}>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Home />} />
            <Route path='/docs' element={<Docs />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </div>
  )
}

export default Routing