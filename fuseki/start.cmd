@echo off
rem Canonical Windows launcher. It expects Fuseki 6.2.0 from audit\setup_runtimes.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_fuseki.ps1" %*
