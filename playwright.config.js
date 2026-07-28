import { defineConfig, devices } from '@playwright/test';
import os from 'node:os';
import path from 'node:path';

export default defineConfig({
    testDir: './tests',
    outputDir: path.join(os.tmpdir(), 'leaderboard-image-playwright-results'),
    fullyParallel: false,
    workers: 1,
    timeout: 45_000,
    reporter: [['list']],
    use: {
        baseURL: 'http://127.0.0.1:5055',
        trace: 'retain-on-failure'
    },
    webServer: {
        command: 'python -m flask run --host 127.0.0.1 --port 5055 --no-debugger --no-reload',
        url: 'http://127.0.0.1:5055',
        reuseExistingServer: false,
        timeout: 30_000,
        env: {
            FLASK_APP: 'app.py',
            SECRET_KEY: 'local-playwright-qa-secret'
        }
    },
    projects: [
        {
            name: 'desktop-chromium',
            use: {
                ...devices['Desktop Chrome'],
                viewport: { width: 1440, height: 1000 }
            }
        },
        {
            name: 'mobile-chromium',
            use: {
                ...devices['Pixel 7']
            }
        }
    ]
});
