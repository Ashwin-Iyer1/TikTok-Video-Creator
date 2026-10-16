const {defineConfig}=require('@playwright/test');
module.exports=defineConfig({testDir:'tests',testMatch:'*.spec.cjs',workers:1,timeout:60000,use:{headless:true},webServer:{command:'python run.py studio --port 8841 --workspace workspace/browser-qa',url:'http://127.0.0.1:8841',reuseExistingServer:false},reporter:'list'});
