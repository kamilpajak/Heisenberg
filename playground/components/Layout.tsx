import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Github, Microscope, Copy, Check } from 'lucide-react';
import { useState } from 'react';

export const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [copied, setCopied] = useState(false);
  const [installMode, setInstallMode] = useState<'npm' | 'pip'>('npm');
  const location = useLocation();

  const command = installMode === 'npm' ? 'npx heisenberg' : 'pip install heisenberg';

  const handleCopyInstall = () => {
    navigator.clipboard.writeText(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col">
      <header className="sticky top-0 z-50 bg-slate-900/80 backdrop-blur-md border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Link to="/" className="flex items-center gap-2 group">
              <div className="p-2 bg-indigo-500/10 rounded-lg group-hover:bg-indigo-500/20 transition-colors">
                <Microscope className="w-6 h-6 text-indigo-400" />
              </div>
              <span className="text-xl font-bold bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">
                Heisenberg
              </span>
            </Link>

            <div className="flex items-center gap-4">
               {/* Install CTA with Toggle */}
              <div className="hidden md:flex items-center gap-3 px-2 py-1.5 bg-slate-800 rounded-lg border border-slate-700">
                
                {/* Toggle Switch */}
                <div className="flex bg-slate-900 rounded p-0.5 border border-slate-700/50">
                    <button 
                        onClick={() => setInstallMode('npm')}
                        className={`px-2 py-0.5 text-[10px] font-bold rounded transition-all ${
                            installMode === 'npm' 
                            ? 'bg-slate-700 text-white shadow-sm' 
                            : 'text-slate-500 hover:text-slate-300'
                        }`}
                    >
                        NPM
                    </button>
                    <button 
                        onClick={() => setInstallMode('pip')}
                        className={`px-2 py-0.5 text-[10px] font-bold rounded transition-all ${
                            installMode === 'pip' 
                            ? 'bg-slate-700 text-white shadow-sm' 
                            : 'text-slate-500 hover:text-slate-300'
                        }`}
                    >
                        PIP
                    </button>
                </div>

                <div className="flex items-center gap-2 pr-1">
                    <span className="text-slate-300 text-sm font-mono min-w-[140px] text-center">
                        {installMode === 'npm' ? '$ npx heisenberg' : '$ pip install heisenberg'}
                    </span>
                    <button 
                    onClick={handleCopyInstall}
                    className="p-1.5 hover:bg-slate-700 rounded transition-colors text-slate-400 hover:text-white"
                    aria-label="Copy install command"
                    title="Copy to clipboard"
                    >
                    {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                </div>
              </div>

              <a 
                href="https://github.com/kamilpajak/Heisenberg" 
                target="_blank"
                rel="noreferrer"
                className="text-slate-400 hover:text-white transition-colors"
              >
                <Github className="w-6 h-6" />
              </a>
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      <footer className="border-t border-slate-800 bg-slate-950">
        <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8 flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-slate-500 text-sm">
            Heisenberg demonstrates AI diagnosis on real GitHub snapshots. Data is static for demo purposes.
          </p>
          <div className="flex gap-6">
            <a href="#" className="text-slate-500 hover:text-indigo-400 text-sm">Documentation</a>
            <a href="#" className="text-slate-500 hover:text-indigo-400 text-sm">Privacy</a>
          </div>
        </div>
      </footer>
    </div>
  );
};