import React from 'react';
import { Routes, Route, HashRouter  } from "react-router-dom";
import { Docs, Home, Layout } from './pages';


const Routing = () => {
  return (
    <div>
      <HashRouter basename='/'>
        <Routes>
          <Route path="/" element={<Layout />}> {/* put url base here and nest children routes */}
            <Route index element={<Home />} />
            <Route path='/docs' element={<Docs />} />
          </Route>
        </Routes>
      </HashRouter >
    </div>
  )
}

export default Routing