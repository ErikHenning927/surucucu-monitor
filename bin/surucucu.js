#!/usr/bin/env node
const { spawn } = require('child_process');
const path = require('path');

const repoSrc = path.join(__dirname, '..', 'src');
const env = { ...process.env };
env.PYTHONPATH = env.PYTHONPATH ? `${repoSrc}:${env.PYTHONPATH}` : repoSrc;

const proc = spawn('python3', ['-m', 'surucucu', ...process.argv.slice(2)], {
  stdio: 'inherit',
  env: env
});

proc.on('exit', (code) => {
  process.exit(code || 0);
});
