import React, { useEffect, useState, useRef } from 'react';

interface Props {
  logs: string[];
  typingSpeed?: number;
  className?: string;
}

// Helper to apply colors to parts of the string
const formatLine = (text: string, index: number) => {
  // 1. Command Line ($ ...)
  if (text.startsWith('$')) {
    return (
      <span key={index}>
        <span className="text-pink-400 font-bold">$</span>
        <span className="text-slate-200">{text.substring(1)}</span>
      </span>
    );
  }

  // 2. Success/Headers
  if (text.includes('DIAGNOSIS COMPLETE')) {
    return <span key={index} className="text-emerald-400 font-bold">{text}</span>;
  }
  if (text.startsWith('> Root Cause:')) {
    return (
      <span key={index}>
        <span className="text-cyan-400 font-semibold">Root Cause:</span>
        <span className="text-slate-300">{text.replace('> Root Cause:', '')}</span>
      </span>
    );
  }
  if (text.startsWith('> Fix:')) {
    return (
      <span key={index}>
        <span className="text-cyan-400 font-semibold">Fix:</span>
        <span className="text-slate-300">{text.replace('> Fix:', '')}</span>
      </span>
    );
  }

  // 3. Highlight quoted strings (simple regex)
  const parts = text.split(/('.*?')/g);
  return (
    <span key={index} className="text-slate-400">
      {parts.map((part, i) => {
        if (part.startsWith("'") && part.endsWith("'")) {
          return <span key={i} className="text-amber-300">{part}</span>;
        }
        // Highlight prompt carats
        if (part.trim() === '>') {
             return <span key={i} className="text-slate-600 font-bold mr-2">{part}</span>;
        }
        return <span key={i}>{part}</span>;
      })}
    </span>
  );
};

export const TerminalView: React.FC<Props> = ({ logs, typingSpeed = 30, className = '' }) => {
  const [displayedContent, setDisplayedContent] = useState<string>('');
  const [currentIndex, setCurrentIndex] = useState(0);
  const [charIndex, setCharIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (currentIndex >= logs.length) return;

    const currentLine = logs[currentIndex];
    
    if (charIndex < currentLine.length) {
      const timeout = setTimeout(() => {
        setDisplayedContent(prev => prev + currentLine[charIndex]);
        setCharIndex(prev => prev + 1);
      }, typingSpeed);
      return () => clearTimeout(timeout);
    } else {
        setDisplayedContent(prev => prev + '\n');
        setCurrentIndex(prev => prev + 1);
        setCharIndex(0);
    }
  }, [currentIndex, charIndex, logs, typingSpeed]);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [displayedContent]);

  // Split displayed content back into lines for formatting
  const lines = displayedContent.split('\n');

  return (
    <div className={`rounded-xl overflow-hidden border border-slate-800 bg-[#0d1117] font-mono text-sm shadow-xl flex flex-col ${className}`}>
      {/* Simplified Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#161b22] border-b border-slate-800/50 shrink-0">
         <span className="text-xs text-slate-500 font-mono flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-indigo-500/50"></span>
            heisenberg-cli
         </span>
         <span className="text-[10px] text-slate-600 uppercase tracking-wider">ReadOnly</span>
      </div>

      {/* Terminal Body */}
      <div 
        ref={containerRef}
        className="p-4 overflow-y-auto flex-1 font-mono leading-relaxed"
      >
        {lines.map((line, idx) => (
            // Only render line if it's not the empty string from the last split (unless it's the only one)
            (line || idx === 0) ? (
                <div key={idx} className="min-h-[1.5em] break-words">
                   {formatLine(line, idx)}
                   {/* Cursor only on the last active line */}
                   {idx === lines.length - 1 && currentIndex < logs.length && (
                      <span className="animate-pulse inline-block w-2.5 h-4 bg-slate-500 align-middle ml-1" />
                   )}
                </div>
            ) : null
        ))}
      </div>
    </div>
  );
};