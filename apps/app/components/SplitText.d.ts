import type { ReactElement } from 'react';

export interface SplitTextProps {
  text: string;
  className?: string;
  delay?: number;
  duration?: number;
  ease?: string;
  splitType?: string;
  from?: Record<string, string | number>;
  to?: Record<string, string | number>;
  threshold?: number;
  rootMargin?: string;
  textAlign?: 'left' | 'center' | 'right';
  tag?: keyof React.JSX.IntrinsicElements;
  staggerFrom?: string;
  mask?: boolean;
  effect?: string;
  trigger?: string;
  loop?: boolean;
  loopDelay?: number;
  hoverEffect?: string;
  color?: string;
  accentColor?: string;
  onLetterAnimationComplete?: () => void;
}

declare const SplitText: (props: SplitTextProps) => ReactElement;

export default SplitText;
