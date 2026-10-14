# Attendly Atelier design and attribution

## Purpose
Attendly Atelier is an original, responsive Django-template interface for the existing business logic. It modernizes the administrative dashboard, attendance time clock, team directory, login, marketing styles and navigation. No changes to attendance, billing, tenant scoping or migrations are made.

## Open-source research
Design patterns were studied from publicly accessible GitHub projects:
- [shadcn/ui](https://github.com/shadcn-ui/ui) — MIT — accessible, composable form, button and card design principles.
- [Tabler](https://github.com/tabler/tabler) — MIT — dashboard density, navigation rhythm and legibility.
- [shadcn-admin](https://github.com/satnaing/shadcn-admin) — MIT — dashboard layout patterns and information hierarchy.
- [Lucide](https://github.com/lucide-icons/lucide) — ISC — clean, consistent line iconography.

The implementation is written as first-party HTML/CSS/JavaScript, not transplanted React components or templates. The tiny inline SVG icon set follows Lucide iconographic conventions. Its attribution is recorded below.

## License for Lucide-inspired inline SVG icons
Copyright (c) 2026 Lucide Icons and Contributors

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

## Design tokens
- Background: off-white #f8f9fc with a soft lavender / blue radial canvas.
- Sidebar: midnight-indigo #171a30 with subtle gradients.
- Brand action: electric violet #635bff; employee punch action: teal.
- Cards: white, low-contrast borders, 20px radii, restrained shadows.
- Type: local system UI font stack, no remote font downloads.
- Responsive: 1250px compact metrics, 920px accessible mobile navigation, 700/480px narrow content layout.
- Accessibility: semantic main/navigation, high-visibility focus indicator, user motion preference, focus trap for sidebar, accessible labels, responsive tables.

## Preview checklist
1. Log in to company dashboard and employee time clock on desktop and a narrow phone viewport.
2. Verify clocks use *device-local display time* and server-stored actions; confirm that role navigation is correct.
3. Verify clock-in / breaks / clock-out, shifts, employee invitations, leave, reports, admin settings, company billing access.
4. Test mobile hamburger (open, backdrop close, escape, tab trapping); check text zoom and keyboard navigation.
5. Check static assets and page runtime logs, not just a successful build. Review contrast and touch targets.
6. Keep a separate preview release until owner approves. Existing staging production stays unaffected.

No third-party CDNs, image hotlinks, tracking pixels, font files, or vendor JS have been added.
