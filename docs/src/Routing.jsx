import React from 'react';
import { Routes, Route, BrowserRouter } from "react-router-dom";
import { Docs, Home, Layout } from './pages';


const Routing = () => {
  return (
    <div>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Home />} />
            <Route path='docs' element={<Docs />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </div>
  )
}

export default Routing