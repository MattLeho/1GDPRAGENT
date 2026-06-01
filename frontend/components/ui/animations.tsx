"use client";

/**
 * Animation Components using Framer Motion
 * 
 * Provides reusable animation primitives for consistent UX:
 * - Page transitions
 * - Card/item enter animations
 * - Fade/slide effects
 * - Stagger animations for lists
 */

import { motion, AnimatePresence, Variants } from "framer-motion";
import { ReactNode } from "react";

// =============================================================================
// Animation Variants
// =============================================================================

export const fadeIn: Variants = {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
};

export const fadeInUp: Variants = {
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -10 },
};

export const fadeInDown: Variants = {
    initial: { opacity: 0, y: -20 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: 10 },
};

export const slideInLeft: Variants = {
    initial: { opacity: 0, x: -30 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: -20 },
};

export const slideInRight: Variants = {
    initial: { opacity: 0, x: 30 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: 20 },
};

export const scaleIn: Variants = {
    initial: { opacity: 0, scale: 0.95 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.98 },
};

export const staggerContainer: Variants = {
    initial: {},
    animate: {
        transition: {
            staggerChildren: 0.08,
            delayChildren: 0.1,
        },
    },
};

export const staggerItem: Variants = {
    initial: { opacity: 0, y: 15 },
    animate: { opacity: 1, y: 0 },
};

// =============================================================================
// Page Transition Components
// =============================================================================

interface PageTransitionProps {
    children: ReactNode;
    className?: string;
}

export function PageTransition({ children, className }: PageTransitionProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className={className}
        >
            {children}
        </motion.div>
    );
}

export function PageFade({ children, className }: PageTransitionProps) {
    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className={className}
        >
            {children}
        </motion.div>
    );
}

// =============================================================================
// Card & Item Animations
// =============================================================================

interface AnimatedCardProps {
    children: ReactNode;
    className?: string;
    delay?: number;
}

export function AnimatedCard({ children, className, delay = 0 }: AnimatedCardProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay, ease: "easeOut" }}
            className={className}
        >
            {children}
        </motion.div>
    );
}

export function AnimatedListItem({ children, className, delay = 0 }: AnimatedCardProps) {
    return (
        <motion.div
            variants={staggerItem}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className={className}
        >
            {children}
        </motion.div>
    );
}

// =============================================================================
// Stagger Container
// =============================================================================

interface StaggerContainerProps {
    children: ReactNode;
    className?: string;
    staggerDelay?: number;
}

export function StaggerContainer({
    children,
    className,
    staggerDelay = 0.08
}: StaggerContainerProps) {
    return (
        <motion.div
            initial="initial"
            animate="animate"
            variants={{
                initial: {},
                animate: {
                    transition: {
                        staggerChildren: staggerDelay,
                        delayChildren: 0.1,
                    },
                },
            }}
            className={className}
        >
            {children}
        </motion.div>
    );
}

// =============================================================================
// Interactive Animations
// =============================================================================

interface HoverScaleProps {
    children: ReactNode;
    className?: string;
    scale?: number;
}

export function HoverScale({ children, className, scale = 1.02 }: HoverScaleProps) {
    return (
        <motion.div
            whileHover={{ scale }}
            whileTap={{ scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className={className}
        >
            {children}
        </motion.div>
    );
}

// =============================================================================
// Appearance Animations
// =============================================================================

interface AppearProps {
    children: ReactNode;
    className?: string;
    when?: boolean;
}

export function Appear({ children, className, when = true }: AppearProps) {
    return (
        <AnimatePresence mode="wait">
            {when && (
                <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.2 }}
                    className={className}
                >
                    {children}
                </motion.div>
            )}
        </AnimatePresence>
    );
}

export function FadePresence({ children, className, when = true }: AppearProps) {
    return (
        <AnimatePresence mode="wait">
            {when && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.15 }}
                    className={className}
                >
                    {children}
                </motion.div>
            )}
        </AnimatePresence>
    );
}

// =============================================================================
// Node Animations (for Graph)
// =============================================================================

interface NodeAppearProps {
    children: ReactNode;
    className?: string;
    delay?: number;
}

export function NodeAppear({ children, className, delay = 0 }: NodeAppearProps) {
    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.5 }}
            transition={{
                duration: 0.3,
                delay,
                type: "spring",
                stiffness: 300,
                damping: 20
            }}
            className={className}
        >
            {children}
        </motion.div>
    );
}
