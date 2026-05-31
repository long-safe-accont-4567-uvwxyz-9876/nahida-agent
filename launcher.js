const { spawn } = require('child_process');
const path = require('path');
const os = require('os');

const isWindows = os.platform() === 'win32';
const pythonCmd = isWindows ? 'python' : 'python3';

function startAgent(mode = 'cli') {
    const scripts = {
        cli: 'agent.py',
        bot: 'qq_bot_adapter.py',
        web: 'web/app.py',
    };

    const script = scripts[mode] || scripts.cli;
    console.log(`🌿 启动纳西妲 AI Agent (${mode} 模式)...`);

    const child = spawn(pythonCmd, [script], {
        cwd: __dirname,
        stdio: 'inherit',
        shell: true,
    });

    child.on('close', (code) => {
        console.log(`\n🌿 纳西妲已退出 (code: ${code})`);
    });

    child.on('error', (err) => {
        console.error('启动失败:', err.message);
    });
}

const mode = process.argv[2] || 'cli';
startAgent(mode);
