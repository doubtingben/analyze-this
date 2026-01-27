# Flutter App UI Refresh Design

## Overview

Update the Flutter app's visual design to align with the web dashboard and Expo mobile app, using a hybrid approach that combines mobile-native UX patterns with clean visual simplicity.

## Scope

**In scope (this iteration):**
- Theme system with unified colors
- Typography scale
- Card-based item display with elevation
- Neutral type badges with icons
- Light mode only

**Out of scope (future iterations):**
- Tab navigation
- Search bar
- Pull-to-refresh
- Dark mode
- Timeline "Now" divider
- Parallax headers

## Design Decisions

### Color Palette

| Token | Value | Usage |
|-------|-------|-------|
| Primary | `#0a7ea4` | Buttons, links, active states |
| Background | `#f5f5f5` | Scaffold background |
| Surface | `#ffffff` | Cards, AppBar |
| Text Primary | `#11181C` | Headlines, body text |
| Text Secondary | `#687076` | Metadata, timestamps |
| Badge Background | `#f3f4f6` | Type badges |
| Badge Text | `#374151` | Badge labels |

### Typography

- System fonts (platform default)
- Title: 20px, weight 600
- Card title: 16px, weight 600
- Body: 14px, weight 400
- Metadata: 12px, weight 500
- Timestamp: 12px, weight 400, secondary color

### Spacing Scale

- xs: 4px
- sm: 8px
- md: 12px
- lg: 16px
- xl: 20px
- xxl: 24px

### Card Design

- Background: white
- Border radius: 12px
- Elevation: 2 (subtle shadow)
- Padding: 16px
- Gap between cards: 12px

### Type Badges

- Neutral styling (no color coding)
- Icon + text layout
- Background: light gray
- Border radius: 4px

## File Changes

1. **lib/theme/app_theme.dart** (new) - Theme configuration
2. **lib/theme/app_colors.dart** (new) - Color constants
3. **lib/theme/app_typography.dart** (new) - Text styles
4. **lib/theme/app_spacing.dart** (new) - Spacing constants
5. **lib/widgets/history_card.dart** (new) - Card component
6. **lib/widgets/type_badge.dart** (new) - Badge component
7. **lib/main.dart** - Update to use new theme and widgets
