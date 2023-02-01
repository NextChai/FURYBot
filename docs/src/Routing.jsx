import React from 'react';
import { Routes, Route, HashRouter  } from "react-router-dom";
import { Docs, Home, Layout } from './pages';


const Routing = () => {
  return (
    <div>
      <HashRouter basename='/Fury-Bot'>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Home />} />
            <Route path='/docs' element={<Docs />} />
          </Route>
        </Routes>
      </HashRouter >
    </div>
  )
}

export default Routing