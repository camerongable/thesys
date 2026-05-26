# Thesys Design System

Thesys uses a compact command-center interface for evidence-backed strategy work. The system is inspired by dark workflow tools such as Linear, but the tokens and usage below are app-specific.

## Theme

Dark mode is the primary theme. Light mode remains available for users who prefer it.

## Core Tokens

The light and dark palettes use the same semantic tokens. Theme changes adjust brightness and contrast, not product identity.

| Token | Light value | Dark value | Role |
| --- | --- | --- | --- |
| Canvas | `#f7f8f8` | `#08090a` | Page background |
| Card | `#ffffff` | `#0f1011` | Primary content surface |
| Surface | `#eef0f1` | `#161718` | Elevated or nested surface |
| Border | `#d0d6e0` | `#23252a` | Cards, inputs, dividers |
| Muted | `#e5e5e6` | `#383b3f` | Subtle controls and badges |
| Text | `#08090a` | `#f7f8f8` | Primary text |
| Text muted | `#62666d` | `#8a8f98` | Labels, descriptions, inactive states |
| Primary | dark lime | `#e4f222` | Accessible links, icons, focus, navigation |
| Action | `#9fad2e` | `#e4f222` | Filled primary calls to action |
| Success | `#27a644` | `#27a644` | Completed and positive status |
| Warning | amber/lime | amber/lime | At-risk status |
| Danger | `#eb5757` | `#eb5757` | Off-track and error status |

Implementation lives in `apps/web/src/app/globals.css` as CSS variables and is exposed to Tailwind in `apps/web/tailwind.config.js`.

## Typography

Use `Inter Variable` when available, then Inter/system UI fallbacks. Use `Berkeley Mono`/monospace fallbacks only for code, IDs, and data that benefits from fixed character widths.

Keep text compact and readable:

| Role | Size |
| --- | --- |
| Caption | `10px` to `12px` |
| Body | `14px` |
| Section heading | `16px` to `24px` |
| Page heading | `24px` to `32px` |

Letter spacing stays normal across the app.

## Layout

Use compact spacing:

| Token | Value |
| --- | --- |
| Base unit | `4px` |
| Element gap | `8px` |
| Section gap | `24px` |
| Card padding | `12px` to `20px` |
| Default radius | `6px` |

Avoid large empty dashboards. Prefer compact rows, status tables, and progressive disclosure.

## Components

Primary button:
Use `action` only for the obvious next action on the screen. This is neon lime with dark text in both themes.

Selected action controls:
Use `action` with `action-foreground` for selected filter pills, segmented controls, and other filled action states. Text and icons on yellow/citron fills should stay dark for contrast; do not use pale text on action fills.

Primary links and icons:
Use `primary`, a darker lime in light mode and neon lime in dark mode, so links and icons remain readable while preserving the same accent family.

Secondary button:
Muted surface, border, foreground text. Use for alternate actions and filters.

Cards:
Use `card` surfaces with `border`. Nested content should use `muted` or `surface`, not another heavy card unless it frames repeated items.

Badges:
Use muted badges for metadata. Use success/warning/danger only for state.

Inputs:
Use transparent or input-token backgrounds with border and primary focus ring.

## Status Language

Use health/status signals consistently:

- `On track`: clear state, enough evidence, no immediate blocking risk.
- `At risk`: weak evidence, low confidence, or material validation risk.
- `Off track`: killed, failed, or strategically invalidated.
- `Paused`: intentionally stopped, no active next action.

## Dark Mode

Theme is controlled by the `dark` class on `<html>`. The app stores the user choice in `localStorage` under `thesys-theme`; if no choice exists, it follows the OS color preference.
