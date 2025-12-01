const { app, BrowserWindow } = require('electron');
const { exec } = require('child_process');

function createWindow() {
  let win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: { nodeIntegration: false }
  });

  exec('python app.py'); // start Flask in background
  setTimeout(() => win.loadURL('http://127.0.0.1:5000'), 2000);
}

app.whenReady().then(createWindow);
