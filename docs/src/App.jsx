import React from 'react';
import { Navbar, Hero } from './components';
import styles from "./style";

const App = () => {
  return (
    <div className="w-full overflow-hidden bg-light-bg dark:bg-dark-bg">
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