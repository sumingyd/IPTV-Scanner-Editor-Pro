const {app,BrowserWindow}=require('electron');
const path=require('path');
const express=require('express');
const {spawnChild}=require('child_process');

const PORT=process.env.PORT||2699;
const HOST=process.env.HOST||'127.0.0.1';

const nodeServerPath=path.join(__dirname,'..');
let nodeProcess=null;

function startNodeServer(){
  const indexJs=path.join(nodeServerPath,'index.js');
  nodeProcess=spawnChild('node',[indexJs],{workingDirectory:nodeServerPath,env:{...process.env,PORT:STRING(PORT)},stdio:'ignore',stderr:'ignore'});
  nodeProcess.on('error',(e)=>console.error('Node process error:',e));
}

function createWindow(){
  const win=new BrowserWindow({
    width:1280,height:800,
    webPreferences:{nodeIntegration:false,contextIsolation:false},
    show:false,
    title:'IPTV Player',
    icon:path.join(__dirname,'../resources/logo.ico')
  });
  win.loadURL(`http://${HOST}:${PORT}/player.html`);
  win.once('ready-to-show',()=>win.show());
  win.on('closed',()=>{if(nodeProcess){nodeProcess.kill();nodeProcess=null;}app.quit();});
}

app.on('ready',()=>{startNodeServer();setTimeout(createWindow,1500);});
app.on('window-all-closed',()=>{if(nodeProcess){nodeProcess.kill();nodeProcess=null;}app.quit();});