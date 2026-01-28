import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { GitCommit, Calendar, Star, Search, Filter, ExternalLink, ArrowRight, HelpCircle } from 'lucide-react';
import { Manifest, ConfidenceLevel, CaseSummary } from '../types';
import { fetchManifest } from '../services/dataService';
import { ConfidenceBadge } from '../components/ConfidenceBadge';
import { TerminalView } from '../components/TerminalView';

const timeAgo = (dateString: string) => {
  const date = new Date(dateString);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  
  let interval = seconds / 31536000;
  if (interval > 1) return Math.floor(interval) + " years ago";
  interval = seconds / 2592000;
  if (interval > 1) return Math.floor(interval) + " months ago";
  interval = seconds / 86400;
  if (interval > 1) return Math.floor(interval) + " days ago";
  interval = seconds / 3600;
  if (interval > 1) return Math.floor(interval) + " hours ago";
  return "Just now";
};

export const Dashboard: React.FC = () => {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [filter, setFilter] = useState<ConfidenceLevel | 'ALL'>('ALL');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchManifest().then(data => {
      setManifest(data);
      setLoading(false);
    });
  }, []);

  if (loading || !manifest) {
    return (
        <div className="flex h-64 items-center justify-center">
             <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
        </div>
    );
  }

  const filteredCases = manifest.cases.filter(
    c => filter === 'ALL' || c.confidence === filter
  );

  const heroLogs = [
    "$ heisenberg diagnose --repo enso-org/enso",
    "> Connecting to GitHub Actions...",
    "> Fetching recent failures from run #123456...",
    "> Analyzing failure: 'Should connect to language server'...",
    "> Checking log artifacts...",
    "> Inspecting source code...",
    "> ",
    "> DIAGNOSIS COMPLETE (99% CONFIDENCE):",
    "> Root Cause: Race condition in WebSocket initialization.",
    "> Fix: Await 'open' event before sending messages."
  ];

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Hero / Stats Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-stretch">
        <div className="flex flex-col justify-center space-y-6">
          <h1 className="text-4xl font-bold text-white leading-tight">
            Stop digging through logs. <br />
            <span className="text-indigo-400">Start fixing.</span>
          </h1>
          <p className="text-slate-300 text-lg leading-relaxed max-w-xl">
            Heisenberg uses AI to instantly diagnose Playwright test failures.
            It transforms cryptic stack traces into clear, actionable root cause analysis.
          </p>
        </div>

        {/* Hero Terminal */}
        <div className="h-[320px] shadow-2xl shadow-indigo-500/10">
           <TerminalView logs={heroLogs} typingSpeed={25} className="h-full border-slate-600/50" />
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-col sm:flex-row justify-between items-center gap-4 py-6 border-b border-slate-800 mt-8">
        <h2 className="text-xl font-semibold text-white flex items-center gap-2">
            <GitCommit className="text-indigo-400" />
            Recent Analysis
        </h2>
        <div className="flex items-center gap-2 bg-slate-800 p-1 rounded-lg">
            <Filter className="w-4 h-4 text-slate-400 ml-2" />
            {([
                'ALL', 
                ConfidenceLevel.HIGH, 
                ConfidenceLevel.MEDIUM, 
                ConfidenceLevel.LOW
            ] as const).map((level) => (
                <button
                    key={level}
                    onClick={() => setFilter(level)}
                    className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
                        filter === level 
                        ? 'bg-slate-600 text-white shadow-sm' 
                        : 'text-slate-400 hover:text-white hover:bg-slate-700'
                    }`}
                >
                    {level}
                </button>
            ))}
        </div>
      </div>

      {/* Grid of Cases */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredCases.map((item) => (
          <Link 
            key={item.id} 
            to={`/case/${item.id}`}
            className="group bg-slate-800/40 border border-slate-700 rounded-xl p-5 hover:border-indigo-500/50 hover:bg-slate-800/80 transition-all duration-200 flex flex-col relative overflow-hidden"
          >
            {/* Hover glow effect */}
            <div className="absolute top-0 right-0 -mr-16 -mt-16 w-32 h-32 bg-indigo-500/10 rounded-full blur-3xl group-hover:bg-indigo-500/20 transition-all"></div>

            <div className="flex justify-between items-start mb-4 relative z-10">
               <div>
                  <h3 className="text-lg font-bold text-white group-hover:text-indigo-400 transition-colors flex items-center gap-2">
                      {item.repoName}
                  </h3>
                  <p className="text-slate-400 text-xs font-mono mt-0.5">{item.repoOwner}</p>
               </div>
               <ConfidenceBadge level={item.confidence} />
            </div>

            <p className="text-slate-300 text-sm leading-relaxed line-clamp-3 mb-6 flex-grow">
               "{item.rootCausePreview}"
            </p>

            <div className="flex items-center justify-between pt-4 border-t border-slate-700/50 text-xs text-slate-500 mt-auto relative z-10">
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5" title="Stars">
                        <Star className="w-3.5 h-3.5" />
                        {item.stars.toLocaleString()}
                    </div>
                    <div className="flex items-center gap-1.5" title="Analyzed">
                        <Calendar className="w-3.5 h-3.5" />
                        {timeAgo(item.snapshotDate)}
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <a 
                        href={item.githubActionsUrl}
                        target="_blank"
                        rel="noreferrer" 
                        onClick={(e) => e.stopPropagation()}
                        className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white transition-colors"
                        title="View Original Actions Run"
                    >
                        <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                    <span className="text-indigo-400 opacity-0 group-hover:opacity-100 transition-opacity transform translate-x-2 group-hover:translate-x-0">
                        <ArrowRight className="w-4 h-4" />
                    </span>
                </div>
            </div>
          </Link>
        ))}
        {filteredCases.length === 0 && (
            <div className="col-span-full py-12 text-center text-slate-500">
                No cases found for this filter.
            </div>
        )}
      </div>
    </div>
  );
};