'use client';

import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';
import { format, addDays, subDays } from 'date-fns';

interface HeaderProps {
  title: string;
  date?: Date;
  onDateChange?: (date: Date) => void;
  showDatePicker?: boolean;
}

export function Header({ title, date, onDateChange, showDatePicker = true }: HeaderProps) {
  const today = new Date();
  const isToday = date ? format(date, 'yyyy-MM-dd') === format(today, 'yyyy-MM-dd') : true;

  const handlePrevDay = () => {
    if (date && onDateChange) {
      onDateChange(subDays(date, 1));
    }
  };

  const handleNextDay = () => {
    if (date && onDateChange && !isToday) {
      onDateChange(addDays(date, 1));
    }
  };

  const handleToday = () => {
    if (onDateChange) {
      onDateChange(today);
    }
  };

  return (
    <header className="h-16 border-b border-slate-800 flex items-center justify-between px-6">
      <h1 className="text-xl font-semibold text-white">{title}</h1>

      {showDatePicker && date && onDateChange && (
        <div className="flex items-center gap-2">
          <button
            onClick={handlePrevDay}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>

          <button
            onClick={handleToday}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 text-white hover:bg-slate-700 transition-colors"
          >
            <Calendar className="w-4 h-4" />
            <span className="text-sm font-medium">
              {isToday ? 'Today' : format(date, 'MMM d, yyyy')}
            </span>
          </button>

          <button
            onClick={handleNextDay}
            disabled={isToday}
            className={`p-2 rounded-lg transition-colors ${
              isToday
                ? 'text-slate-600 cursor-not-allowed'
                : 'text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      )}
    </header>
  );
}
