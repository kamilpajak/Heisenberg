import React from 'react';
import { ConfidenceLevel } from '../types';
import { CheckCircle, Sparkles, HelpCircle } from 'lucide-react';

interface Props {
  level: ConfidenceLevel;
  className?: string;
}

export const ConfidenceBadge: React.FC<Props> = ({ level, className = '' }) => {
  let styles = '';
  let icon = null;
  let description = '';

  switch (level) {
    case ConfidenceLevel.HIGH:
      styles = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      icon = <CheckCircle className="w-3.5 h-3.5 mr-1.5" />;
      description = "High certainty in diagnosis";
      break;
    case ConfidenceLevel.MEDIUM:
      // Changed from Amber (Warning) to Blue (Insight/Value) to reflect that the diagnosis is valuable
      styles = 'bg-blue-500/10 text-blue-400 border-blue-500/20';
      icon = <Sparkles className="w-3.5 h-3.5 mr-1.5" />;
      description = "Moderate certainty - AI insight provided";
      break;
    case ConfidenceLevel.LOW:
      styles = 'bg-slate-700/50 text-slate-400 border-slate-600';
      icon = <HelpCircle className="w-3.5 h-3.5 mr-1.5" />;
      description = "Low certainty - ambiguous failure";
      break;
  }

  return (
    <div 
      className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border cursor-help ${styles} ${className}`}
      title={`AI Confidence Score: How confident the model is in this diagnosis. (${description})`}
    >
      {icon}
      {level} CONFIDENCE
    </div>
  );
};