@echo off
rem Run Fuseki (downloaded by run_fuseki.ps1) from its own folder so it finds its webapp.
cd /d "%~dp0apache-jena-fuseki-3.17.0"
java -Xmx2G -jar fuseki-server.jar --file="%~dp0..\data\gold\vnedu-all.ttl" /vnedu
