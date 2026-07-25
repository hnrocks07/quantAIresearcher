import React, { useState } from 'react';
import { Routes, Route, NavLink } from 'react-router-dom';
import Overview from './pages/Overview';
import Strategies from './pages/Strategies';
import Research from './pages/Research';
import Trading from './pages/Trading';
import Risk from './pages/Risk';
import DataIngestion from './pages/DataIngestion';
import KillSwitch from './pages/KillSwitch';
import AgentMonitor from './pages/AgentMonitor';

export default function App() {
  const [theme, setTheme] = useState('light');

  const toggle = () => {
    const next = theme === 'light' ? 'dark' : 'light';
    setTheme(next);
    document.documentElement.setAttribute('data-theme', next);
  };

  return (
    <div className="app-layout">
      <nav className="sidebar">
        <h2>QUANT CMD</h2>
        <NavLink to="/" end>{'⌂'} Overview</NavLink>
        <NavLink to="/strategies">{'≡'} Strategies</NavLink>
        <NavLink to="/research">{'⌘'} Research</NavLink>
        <NavLink to="/trading">{'⇄'} Trading</NavLink>
        <NavLink to="/risk">{'⚠'} Risk</NavLink>
        <NavLink to="/agents">{'⚙'} Agents</NavLink>
        <NavLink to="/data">{'⇩'} Data</NavLink>
        <NavLink to="/kill-switch">{'⛔'} Kill Switch</NavLink>
      </nav>
      <main className="main-content">
        <div className="page-header">
          <h1>Command Center</h1>
          <button className="theme-toggle" onClick={toggle}>
            {theme === 'light' ? 'Dark' : 'Light'} Mode
          </button>
        </div>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/strategies" element={<Strategies />} />
          <Route path="/research" element={<Research />} />
          <Route path="/trading" element={<Trading />} />
          <Route path="/risk" element={<Risk />} />
          <Route path="/agents" element={<AgentMonitor />} />
          <Route path="/data" element={<DataIngestion />} />
          <Route path="/kill-switch" element={<KillSwitch />} />
        </Routes>
      </main>
    </div>
  );
}
