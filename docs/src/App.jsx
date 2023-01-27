import React from 'react';
import { Navbar, Hero } from './components';
import styles from "./style";

// bg-gradient-to-b from-slate-200 via-sky-900 to-emerald-600

const App = () => {
  return (
    <div className="w-full overflow-hidden bg-white-medium dark:bg-gray-dark">
      <div className={`${styles.paddingX} ${styles.flexCenter}`}>
        <div className={`${styles.boxWidth}`}>
          <Navbar />
        </div>
      </div>

      <div>
        <Hero />
      </div>

    </div>
  )
}

export default App