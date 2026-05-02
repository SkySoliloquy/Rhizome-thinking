/**
 * Rhizome Thinking - Views Module Exports
 *
 * All views have been moved to separate files:
 *   view-outline.js, view-maps.js, view-relationships.js,
 *   view-node-detail.js, view-theme-detail.js, view-theme-evolution.js
 *
 * This file remains for backward compatibility and exports.
 */

// Views are now defined in separate modules and exposed globally
// This file serves as a compatibility layer

// Export references to global view objects (defined in their respective modules)
if (typeof window !== 'undefined') {
    // Ensure all views are available globally
    window.outlineView = window.outlineView || outlineView;
    window.epistemicMapView = window.epistemicMapView || epistemicMapView;
    window.graphView = window.graphView || graphView;
    window.relationshipGraphView = window.relationshipGraphView || relationshipGraphView;
    window.relationshipManagerView = window.relationshipManagerView || relationshipManagerView;
    window.NodeDetailView = window.NodeDetailView || NodeDetailView;
    window.ThemeDetailView = window.ThemeDetailView || ThemeDetailView;
    window.themeEvolutionView = window.themeEvolutionView || themeEvolutionView;
    window.themeConflictView = window.themeConflictView || themeConflictView;
}
