# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

This repository contains a single self-contained static HTML file: `faang_python_full_prep.html`. It is a personal 8-week FAANG Python (senior) interview prep plan/tracker — not an application with source code, dependencies, or a build system.

There is no build, lint, or test tooling. There is no package manager, no server, no framework. To view the page, simply open `faang_python_full_prep.html` directly in a browser.

## Structure of the HTML file

The file is organized as three inline blocks within one `<html>` document:

- `<style>` (top of file): all CSS, using plain class names (no framework/preprocessor). Sections include TOC pills, score cards, callouts, badges, resource pills, week accordions, day grids, and problem list styling.
- Body markup: a table of contents, score/verdict cards, and a series of collapsible "week" blocks (accordion), each containing day cards and problem lists tagged with difficulty/topic badges (DSA, system design, Python, security, project, version, mock interview).
- `<script>` (bottom of file): minimal vanilla JS with two behaviors — `tog(header)` toggles a week accordion open/closed, and a `DOMContentLoaded` listener wires up smooth-scrolling for TOC links to their corresponding section anchors.

When editing, keep everything inline in this single file (no external CSS/JS files, no build step) — that is the intentional design of this document.
