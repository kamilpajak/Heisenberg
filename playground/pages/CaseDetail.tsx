
import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  ArrowLeft, Github, Star, ExternalLink, 
  CheckCircle, AlertTriangle, FileText, Activity, 
  Globe, Image as ImageIcon, Box, Server, 
  ArrowRight, Info, AlertOctagon, Terminal, Minus,
  Lightbulb, Settings, X, Copy, Check, Lock
} from 'lucide-react';
import { fetchCaseData } from '../services/dataService';
import { FullCaseData, DataSource, DataSourceStatus, TimelineEvent, FixSolution, CodeDiff } from '../types';
import { ConfidenceBadge } from '../components/ConfidenceBadge';

// --- SUB-COMPONENTS ---

const SourceIcon: React.FC<{ type: string }> = ({ type }) => {
  switch (type) {
    case 'trace': return <Activity className="w-4 h-4" />;
    case 'log': return <Terminal className="w-4 h-4" />;
    case 'network': return <Globe className="w-4 h-4" />;
    case 'image': return <ImageIcon className="w-4 h-4" />;
    case 'container': return <Box className="w-4 h-4" />;
    case 'server': return <Server className="w-4 h-4" />;
    default: return <FileText className="w-4 h-4" />;
  }
};

const ObservationCard: React.FC<{ source: DataSource; isHovered: boolean }> = ({ source, isHovered }) => {
  let borderClass = 'border-slate-800';
  let bgClass = 'bg-slate-800/40';
  let textClass = 'text-slate-400';
  let statusIcon = <Minus className="w-3.5 h-3.5 text-slate-600" />;

  if (source.status === 'active') {
    borderClass = isHovered ? 'border-emerald-400 ring-1 ring-emerald-400' : 'border-emerald-500/50';
    bgClass = isHovered ? 'bg-emerald-900/20' : 'bg-emerald-900/10';
    textClass = 'text-white';
    statusIcon = <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />;
  } else if (source.status === 'missing') {
    borderClass = 'border-amber-500/50 border-dashed';
    bgClass = 'bg-amber-900/10';
    textClass = 'text-slate-400';
    statusIcon = <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />;
  }

  return (
    <div className={`flex flex-col p-3 rounded-lg border transition-all duration-200 ${borderClass} ${bgClass}`}>
      <div className="flex justify-between items-start mb-2">
        <div className={`p-1.5 rounded-md ${source.status === 'active' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-700/50 text-slate-500'}`}>
          <SourceIcon type={source.iconType} />
        </div>
        {statusIcon}
      </div>
      <span className={`text-xs font-semibold mb-1 truncate ${textClass}`}>{source.name}</span>
      <span className="text-[10px] text-slate-500 leading-tight">{source.insight}</span>
    </div>
  );
};

const TimelineItemView: React.FC<TimelineEvent> = ({ time, label, type, isAnomaly }) => {
  let badgeClass = 'bg-slate-800 text-slate-400 border-slate-700';
  let dotColor = 'bg-slate-600';
  let labelClass = 'font-normal';
  
  if (type === 'trace') {
    badgeClass = 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30';
    dotColor = 'bg-indigo-500';
  } else if (type === 'network') {
    badgeClass = 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30';
    dotColor = 'bg-cyan-500';
  } else if (type === 'console') {
    badgeClass = 'bg-amber-500/10 text-amber-400 border-amber-500/30';
    dotColor = 'bg-amber-500';
    labelClass = 'font-semibold';
  } else if (type === 'error') {
    badgeClass = 'bg-red-500/10 text-red-400 border-red-500/30';
    dotColor = 'bg-red-500';
    labelClass = 'font-bold';
  }

  // Anomaly Override
  if (isAnomaly) {
      badgeClass = 'bg-red-500/10 text-red-400 border-red-500/50 ring-1 ring-red-500/20 shadow-[0_0_10px_rgba(239,68,68,0.2)]';
      dotColor = 'bg-red-500';
      labelClass = 'font-bold text-red-400';
  }

  return (
    <div className="relative pl-8 py-2 group">
      {/* Timeline Line */}
      <div className="absolute left-[11px] top-0 bottom-0 w-px bg-slate-800 group-last:bottom-auto group-last:h-4"></div>
      
      {/* Dot */}
      <div className={`absolute left-[7px] top-4 w-2.5 h-2.5 rounded-full ${dotColor} ring-4 ring-slate-900`}></div>
      
      <div className="flex items-center gap-3">
        <span className="font-mono text-xs text-slate-500 w-12 text-right shrink-0">{time}</span>
        <div className={`text-xs px-2 py-1 rounded border transition-all ${badgeClass} ${labelClass}`}>
           {label}
        </div>
      </div>
    </div>
  );
};

const CodeDiffView: React.FC<{ diff: CodeDiff }> = ({ diff }) => {
    return (
        <div className="bg-[#0d1117] border border-slate-800 rounded-b-xl rounded-tr-xl overflow-hidden font-mono text-xs flex flex-col w-full">
            <div className="grid grid-cols-2 divide-x divide-slate-800 border-b border-slate-800 shrink-0">
                <div className="bg-red-900/10 text-red-400 p-2 text-center font-semibold">Before</div>
                <div className="bg-green-900/10 text-emerald-400 p-2 text-center font-semibold">After</div>
            </div>
            <div className="grid grid-cols-2 divide-x divide-slate-800 overflow-y-auto max-h-[500px] w-full relative">
                {/* Original */}
                <div className="p-4 bg-red-900/5 overflow-x-hidden min-h-full">
                    <pre className="text-red-300 leading-relaxed whitespace-pre-wrap break-all font-mono">
                        {diff.originalContent}
                    </pre>
                </div>
                {/* Modified */}
                <div className="p-4 bg-green-900/5 overflow-x-hidden min-h-full relative group">
                    <div className="sticky top-0 z-10 flex justify-end h-0 overflow-visible pointer-events-none">
                         <span className="mt-2 mr-2 text-[10px] bg-emerald-900/50 text-emerald-400 px-2 py-1 rounded border border-emerald-500/20 shadow-lg backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-opacity pointer-events-auto">
                            Fix applied
                        </span>
                    </div>
                    <pre className="text-emerald-300 leading-relaxed whitespace-pre-wrap break-all font-mono">
                        {diff.modifiedContent}
                    </pre>
                </div>
            </div>
        </div>
    );
}

const AnalyzeRepoModal: React.FC<{ isOpen: boolean; onClose: () => void }> = ({ isOpen, onClose }) => {
  const [step, setStep] = useState<1 | 2>(1);
  const [repoUrl, setRepoUrl] = useState('');
  const [copied, setCopied] = useState(false);

  // Reset state when opened
  useEffect(() => {
      if (isOpen) {
          setStep(1);
          setRepoUrl('');
          setCopied(false);
      }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleGenerate = () => {
       if (repoUrl.trim().length > 0) {
           setStep(2);
       }
  };

  const command = `pip install heisenberg && heisenberg fetch-github --repo ${repoUrl}`;

  const handleCopy = () => {
      navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
  };

  return (
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 animate-fade-in">
          {/* Backdrop */}
          <div 
              className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm transition-opacity" 
              onClick={onClose}
          ></div>

          {/* Modal Content */}
          <div className="relative w-full max-w-lg bg-[#0f1117] border border-slate-800 rounded-2xl shadow-2xl overflow-hidden transform transition-all">
              <button 
                  onClick={onClose} 
                  className="absolute top-4 right-4 text-slate-500 hover:text-white transition-colors p-2 rounded-full hover:bg-slate-800 z-10"
              >
                  <X className="w-5 h-5" />
              </button>

              <div className="p-8 pt-10">
                  {step === 1 ? (
                      <div className="space-y-8">
                          <div className="text-center space-y-2">
                              <div className="w-12 h-12 bg-indigo-500/10 rounded-xl flex items-center justify-center mx-auto mb-4 border border-indigo-500/20">
                                  <Github className="w-6 h-6 text-indigo-400" />
                              </div>
                              <h2 className="text-2xl font-bold text-white">Analyze your repository</h2>
                              <p className="text-slate-400 text-sm">Enter your GitHub repository URL to start the diagnosis.</p>
                          </div>
                          
                          <div className="space-y-4">
                              <div>
                                  <input
                                      type="text"
                                      value={repoUrl}
                                      onChange={(e) => setRepoUrl(e.target.value)}
                                      placeholder="github.com/owner/repo"
                                      className="w-full bg-slate-800/50 border border-slate-700 rounded-xl px-4 py-3.5 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all font-mono text-sm"
                                      onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
                                      autoFocus
                                  />
                              </div>
                              <button
                                  onClick={handleGenerate}
                                  disabled={!repoUrl.trim()}
                                  className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-3.5 rounded-xl transition-all shadow-lg shadow-indigo-500/20 flex items-center justify-center gap-2 group"
                              >
                                  Generate Command 
                                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                              </button>
                          </div>
                      </div>
                  ) : (
                      <div className="space-y-8">
                          <div className="text-center space-y-3">
                              <h2 className="text-2xl font-bold text-white">Run Heisenberg locally</h2>
                              <div className="flex items-center justify-center gap-1.5 text-emerald-400 text-xs font-medium bg-emerald-500/10 py-1.5 px-3 rounded-full mx-auto w-fit border border-emerald-500/20">
                                  <Lock className="w-3 h-3" />
                                  Your code stays on your machine
                              </div>
                          </div>

                          <div className="relative group">
                              <div className="absolute -inset-0.5 bg-gradient-to-r from-indigo-500 to-cyan-500 rounded-xl opacity-20 group-hover:opacity-30 transition duration-500 blur"></div>
                              <div className="relative bg-slate-900 rounded-xl border border-slate-800 p-5 font-mono text-sm">
                                  <div className="flex justify-between items-start gap-4">
                                      <code className="text-indigo-300 break-all leading-relaxed">
                                          {command}
                                      </code>
                                  </div>
                              </div>
                          </div>

                          <div className="space-y-4">
                              <button
                                  onClick={handleCopy}
                                  className="w-full bg-white hover:bg-slate-100 text-slate-900 font-bold py-3.5 rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-white/5 transform active:scale-[0.98]"
                              >
                                  {copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                                  {copied ? 'Copied to Clipboard' : 'Copy Command'}
                              </button>

                              <div className="text-center pt-2">
                                  <button onClick={() => {}} className="text-xs text-slate-500 hover:text-indigo-400 transition-colors flex items-center justify-center gap-1 mx-auto">
                                      Prefer cloud-hosted? Join the waitlist <ArrowRight className="w-3 h-3" />
                                  </button>
                              </div>
                          </div>
                      </div>
                  )}
              </div>
          </div>
      </div>
  );
};

const FixSection: React.FC<{ fix: FixSolution }> = ({ fix }) => {
    const [activeTab, setActiveTab] = useState(0);

    // Handle config-only case
    if (fix.configChanges && fix.configChanges.length > 0 && (!fix.diffs || fix.diffs.length === 0)) {
        return (
            <div className="bg-[#0d1117] border border-slate-800 rounded-xl p-6">
                <h4 className="text-sm font-bold text-slate-300 flex items-center gap-2 mb-4">
                    <Settings className="w-4 h-4 text-indigo-400" />
                    CONFIGURATION CHANGE
                </h4>
                <div className="space-y-4">
                    {fix.configChanges.map((change, idx) => (
                        <div key={idx} className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                             <div className="flex justify-between items-center mb-2">
                                <span className="font-mono text-xs text-indigo-300">{change.settingName}</span>
                                <span className="text-[10px] text-slate-500 bg-slate-800 px-2 py-1 rounded">{change.reason}</span>
                             </div>
                             <div className="flex items-center gap-3 font-mono text-sm">
                                <span className="text-red-400 line-through">{change.oldValue}</span>
                                <ArrowRight className="w-3 h-3 text-slate-500" />
                                <span className="text-emerald-400 font-bold">{change.newValue}</span>
                             </div>
                        </div>
                    ))}
                </div>
            </div>
        );
    }

    // Handle code diffs
    if (!fix.diffs || fix.diffs.length === 0) {
        return (
            <div className="h-48 bg-slate-800/50 rounded-xl flex items-center justify-center text-slate-500 text-sm">
                No automated fix available for this case.
            </div>
        );
    }

    const hasMultipleFiles = fix.diffs.length > 1;
    const activeDiff = fix.diffs[activeTab];

    // Helper to switch tab if filename clicked in narrative
    const handleNarrativeClick = (e: React.MouseEvent) => {
        const target = e.target as HTMLElement;
        if (target.dataset.filename) {
            const idx = fix.diffs?.findIndex(d => d.fileName === target.dataset.filename);
            if (idx !== undefined && idx !== -1) setActiveTab(idx);
        }
    }

    // Process narrative to make filenames clickable
    const renderNarrative = () => {
        if (!fix.summary) return null;
        
        const words = fix.summary.split(' ');
        return (
            <div className="bg-slate-800/30 border border-slate-700/50 rounded-lg p-3 mb-4 flex items-start gap-3">
                <Lightbulb className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <p className="text-sm text-slate-300 leading-relaxed" onClick={handleNarrativeClick}>
                    {words.map((word, i) => {
                        // Simple strip of punctuation for matching
                        const cleanWord = word.replace(/[.,;:]/g, '');
                        const isFile = fix.diffs?.some(d => d.fileName === cleanWord);
                        const match = fix.diffs?.find(d => d.fileName === cleanWord);
                        
                        if (isFile) {
                            return (
                                <span key={i}>
                                    <span 
                                        className="text-indigo-400 hover:text-indigo-300 cursor-pointer font-mono font-medium border-b border-indigo-500/30 hover:border-indigo-400 transition-colors"
                                        data-filename={cleanWord}
                                    >
                                        {cleanWord}
                                    </span>
                                    {word.slice(cleanWord.length)}{' '}
                                </span>
                            );
                        }
                        return word + ' ';
                    })}
                </p>
            </div>
        );
    };

    return (
        <div>
            {hasMultipleFiles && renderNarrative()}
            
            {/* Tabs (only if multiple files) */}
            {hasMultipleFiles ? (
                <div className="flex items-end gap-1 overflow-x-auto overflow-y-hidden pb-0 pt-2 [&::-webkit-scrollbar]:hidden">
                    {fix.diffs.map((diff, index) => (
                        <button
                            key={index}
                            onClick={() => setActiveTab(index)}
                            className={`
                                relative px-4 py-2 text-xs font-mono font-medium rounded-t-lg border-t border-l border-r transition-all
                                flex items-center gap-2
                                ${activeTab === index 
                                    ? 'bg-[#0d1117] text-white border-slate-800 z-10 bottom-[-1px] border-b-transparent' 
                                    : 'bg-slate-800/50 text-slate-500 border-transparent hover:text-slate-300 hover:bg-slate-800'
                                }
                            `}
                        >
                            {diff.isRootCause && (
                                <span className="w-1.5 h-1.5 rounded-full bg-red-500 shadow-sm shadow-red-500/50" title="Root Cause"></span>
                            )}
                            {diff.fileName}
                        </button>
                    ))}
                    {/* Fill remaining line */}
                    <div className="flex-grow border-b border-slate-800 h-[1px]"></div>
                </div>
            ) : (
                 // Single file case - optional narrative if present, else mostly hidden
                 <div className="flex justify-between items-center mb-2">
                     {/* If single file but has narrative, show it in simplified form? No, per spec, just standard header */}
                     <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded font-mono">{activeDiff.fileName}</span>
                 </div>
            )}
            
            {/* Diff View - Remove top radius if tabs are present */}
            <div className={hasMultipleFiles ? 'rounded-tl-none' : ''}>
                 <CodeDiffView diff={activeDiff} />
            </div>
        </div>
    );
};


// --- MAIN PAGE COMPONENT ---

export const CaseDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<FullCaseData | null>(null);
  const [loading, setLoading] = useState(true);
  const [hoveredSourceId, setHoveredSourceId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    if (id) {
        setLoading(true);
        fetchCaseData(id).then(res => {
            setData(res);
            setLoading(false);
        });
    }
  }, [id]);

  if (loading) {
    return (
        <div className="flex h-screen items-center justify-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-500"></div>
        </div>
    );
  }

  if (!data) return <div className="text-center py-20 text-white">Case not found</div>;

  const handleNarrativeHover = (sourceId: string | null) => {
    setHoveredSourceId(sourceId);
  };

  return (
    <div className="max-w-5xl mx-auto pb-20 animate-fade-in space-y-8">
        <AnalyzeRepoModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />

        {/* 1. HEADER SECTION */}
        <div className="space-y-6 border-b border-slate-800 pb-8">
            <div className="flex items-center justify-between">
                <Link to="/" className="text-slate-400 hover:text-white transition-colors flex items-center gap-2 text-sm">
                    <ArrowLeft className="w-4 h-4" /> Back
                </Link>
                <button 
                    onClick={() => setIsModalOpen(true)}
                    className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-all shadow-lg shadow-indigo-500/20 flex items-center gap-2"
                >
                    Analyze Your Repo <ArrowRight className="w-4 h-4" />
                </button>
            </div>

            <div className="flex flex-col gap-4">
                <div className="flex items-center gap-3 text-slate-400 text-sm">
                    <div className="p-1.5 bg-slate-800 rounded">
                        <Github className="w-4 h-4" />
                    </div>
                    <span className="text-white font-medium">{data.summary.repoOwner} / {data.summary.repoName}</span>
                    <span className="w-1 h-1 bg-slate-600 rounded-full"></span>
                    <span className="flex items-center gap-1"><Star className="w-3.5 h-3.5" /> {data.summary.stars.toLocaleString()}</span>
                    <ConfidenceBadge level={data.diagnosis.confidence} className="ml-2" />
                </div>
                
                <div>
                    <h1 className="text-3xl md:text-4xl font-bold text-white mb-2 leading-tight">
                        {data.diagnosis.verdict || "Analysis Complete"}
                    </h1>
                    <div className="font-mono text-sm text-slate-400 bg-slate-900/50 inline-block px-3 py-1 rounded border border-slate-800">
                        Test: {data.report.failures[0]?.testName}
                    </div>
                </div>
            </div>
        </div>

        {/* 2. OBSERVATION DECK */}
        <div>
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">Observation Deck</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                {data.dataSources?.map((source) => (
                    <ObservationCard 
                        key={source.id} 
                        source={source} 
                        isHovered={hoveredSourceId === source.id}
                    />
                ))}
            </div>
        </div>

        {/* 3 & 4. CONFIDENCE GAP & NARRATIVE */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* 3. CONFIDENCE GAP BOX */}
            <div className="lg:col-span-1 bg-amber-950/10 border border-amber-500/20 rounded-xl p-5 flex flex-col h-full">
                <div className="flex justify-between items-end mb-2">
                    <span className="text-xs font-bold text-amber-500 uppercase tracking-wider">Confidence</span>
                    <span className="text-2xl font-bold text-amber-400">{data.diagnosis.confidenceScore || 85}%</span>
                </div>
                
                {/* Progress Bar */}
                <div className="w-full h-2 bg-slate-800 rounded-full mb-6 overflow-hidden">
                    <div 
                        className="h-full bg-amber-500 transition-all duration-1000 ease-out" 
                        style={{ width: `${data.diagnosis.confidenceScore || 85}%` }}
                    ></div>
                </div>

                {data.confidenceGap && (
                    <>
                        <p className="text-sm text-slate-300 mb-3 font-medium">
                            {data.confidenceGap.message}
                        </p>
                        <ul className="space-y-2 mb-6">
                            {data.confidenceGap.missingSources.map((item, idx) => (
                                <li key={idx} className="flex items-start gap-2 text-xs text-slate-400">
                                    <div className="w-1 h-1 bg-amber-500 rounded-full mt-1.5 shrink-0"></div>
                                    {item}
                                </li>
                            ))}
                        </ul>
                    </>
                )}
                
                <div className="mt-auto pt-4 border-t border-amber-500/10">
                    <button className="text-xs text-amber-400 hover:text-amber-300 font-medium flex items-center gap-1">
                        Learn about data sources <ArrowRight className="w-3 h-3" />
                    </button>
                </div>
            </div>

            {/* 4. AI NARRATIVE */}
            <div className="lg:col-span-2 bg-gradient-to-br from-indigo-900/20 to-slate-900 border border-indigo-500/30 rounded-xl p-6 relative overflow-hidden">
                 <div className="absolute top-0 right-0 p-4 opacity-10">
                    <AlertOctagon className="w-24 h-24 text-indigo-400" />
                 </div>
                 
                 <h3 className="text-xs font-bold text-indigo-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                    <Activity className="w-4 h-4" /> AI Diagnosis
                 </h3>
                 
                 <div className="relative z-10">
                     <div className="text-lg md:text-xl text-slate-200 leading-relaxed font-light font-serif italic">
                        "{data.diagnosis.rootCause}"
                     </div>
                 </div>
            </div>
        </div>

        {/* 5 & 6. EVIDENCE & FIX */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            
            {/* 5. EVIDENCE TIMELINE */}
            <div className="lg:col-span-4 space-y-4">
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Evidence Timeline</h3>
                <div className="bg-[#0f1117] border border-slate-800 rounded-xl p-4">
                    {data.timeline?.map((event, idx) => (
                        <TimelineItemView key={idx} {...event} />
                    ))}
                    {(!data.timeline || data.timeline.length === 0) && (
                        <div className="text-slate-500 text-xs text-center py-4">No timeline data available.</div>
                    )}
                </div>
            </div>

            {/* 6. ROOT CAUSE + FIX */}
            <div className="lg:col-span-8 space-y-4">
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Root Cause & Fix</h3>
                {data.fix && <FixSection fix={data.fix} />}
            </div>
        </div>

        {/* 7. BOTTOM CTA */}
        <div className="mt-12 py-12 border-t border-slate-800 text-center">
            <h2 className="text-2xl font-bold text-white mb-4">Ready to diagnose your own flaky tests?</h2>
            <p className="text-slate-400 mb-8 max-w-lg mx-auto">
                Connect your GitHub repository and let Heisenberg analyze your CI pipelines in real-time.
            </p>
            <button 
                onClick={() => setIsModalOpen(true)}
                className="bg-white hover:bg-slate-200 text-slate-900 px-8 py-3 rounded-full font-bold text-sm transition-all shadow-lg shadow-white/10 hover:shadow-white/20 transform hover:-translate-y-1"
            >
                Analyze Your Repo
            </button>
        </div>

    </div>
  );
};
