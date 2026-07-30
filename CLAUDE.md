# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

This repository contains a single self-contained Markdown file: `python_full_prep.md`. It is a personal 8-week Python (senior) interview prep plan/tracker — not an application with source code, dependencies, or a build system.

There is no build, lint, or test tooling. There is no package manager, no server, no framework. To view the page, open `python_full_prep.md` in any Markdown viewer/editor (or GitHub's own renderer).

## Structure of the Markdown file

Plain Markdown, top to bottom: a title + jump-links line, a diagnostic-scores table, the 2-hour daily schedule table, the Python 3.11→3.14 version-evolution section (per-version feature lists, a feature-availability matrix table, model interview answers), one `##` section per week (1–2 DSA, 3 internals, 4 async, 5 security, 6–7 system design, 8 mocks) each with prose/tables/fenced code blocks, a parallel-tracks section (DSA + project side by side per week), the project component table, and a closing "three things to fix first" section.

When editing, keep everything inline in this single file (no separate assets, no build step) — that is the intentional design of this document.
