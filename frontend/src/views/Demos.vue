<template>
  <div class="demos-container">
    <div class="demos-header">
      <h1>Frontend UI Style Demos (Set 2)</h1>
      <p>另外10种不同风格的前端界面参考 (10 More UI Styles for Reference)</p>
      <el-button @click="$router.push('/')" type="primary" plain>返回主页 (Back Home)</el-button>
    </div>

    <div class="demos-grid">
      
      <!-- 11. Apple / Cupertino -->
      <div class="demo-card card-apple">
        <div class="card-tag">11. 苹果风 (Apple/Cupertino)</div>
        <div class="card-content">
          <h3>Total Revenue</h3>
          <div class="amount">¥ 124,500.00</div>
          <p class="desc">+12.5% from last month</p>
          <button class="action-btn">View Details</button>
        </div>
      </div>

      <!-- 12. Web3 / Crypto -->
      <div class="demo-card card-web3">
        <div class="card-tag">12. Web3 / 加密风</div>
        <div class="card-content">
          <h3>TOTAL REVENUE</h3>
          <div class="amount">¥ 124,500.00</div>
          <p class="desc">+12.5% FROM LAST MONTH</p>
          <button class="action-btn">CONNECT WALLET</button>
        </div>
      </div>

      <!-- 13. Claymorphism -->
      <div class="demo-card card-clay">
        <div class="card-tag">13. 黏土拟物 (Claymorphism)</div>
        <div class="card-content">
          <h3>Total Revenue</h3>
          <div class="amount">¥ 124,500.00</div>
          <p class="desc info">🎉 +12.5% this month</p>
          <button class="action-btn">View Details</button>
        </div>
      </div>

      <!-- 14. Swiss / B&W Brutalism -->
      <div class="demo-card card-swiss">
        <div class="card-tag tag-dark">14. 瑞士极简 (Swiss/B&W)</div>
        <div class="card-content pt">
          <h3 class="swiss-title">01. REVENUE</h3>
          <div class="amount">124,500</div>
          <p class="desc">+12.5%</p>
          <div class="bottom-action">
            <button class="action-btn">VIEW →</button>
          </div>
        </div>
      </div>

      <!-- 15. Aurora / Ambient Glow -->
      <div class="demo-card card-aurora">
        <div class="glow g1"></div>
        <div class="glow g2"></div>
        <div class="card-tag">15. 极光氛围 (Aurora Glow)</div>
        <div class="card-content relative-z">
          <h3>Total Revenue</h3>
          <div class="amount">¥ 124,500.00</div>
          <p class="desc">+12.5% from last month</p>
          <button class="action-btn">View Details</button>
        </div>
      </div>

      <!-- 16. Holographic / Iridescent -->
      <div class="demo-card card-holo">
        <div class="card-tag">16. 镭射全息 (Holographic)</div>
        <div class="card-content">
          <h3>Total Revenue</h3>
          <div class="amount">¥ 124,500.00</div>
          <p class="desc">+12.5% from last month</p>
          <button class="action-btn">View Details</button>
        </div>
      </div>

      <!-- 17. Memphis Design -->
      <div class="demo-card card-memphis">
        <div class="card-tag">17. 孟菲斯 (Memphis 80s)</div>
        <div class="card-content">
          <h3>Total Revenue</h3>
          <div class="amount">¥ 124,500.00</div>
          <p class="desc border-desc">+12.5% ↑</p>
          <button class="action-btn">Details!</button>
        </div>
      </div>

      <!-- 18. Outline / Wireframe -->
      <div class="demo-card card-outline">
        <div class="card-tag">18. 线框蓝图 (Wireframe)</div>
        <div class="card-content">
          <h3>TOTAL_REVENUE</h3>
          <div class="amount">¥ 124,500.00</div>
          <p class="desc">DELTA: +12.5%</p>
          <button class="action-btn">[ VIEW DETAILS ]</button>
        </div>
      </div>

      <!-- 19. Skeuomorphism -->
      <div class="demo-card card-skeuo">
        <div class="card-tag tag-dark">19. 写实拟物 (Skeuomorphism)</div>
        <div class="card-content">
          <div class="inner-screen">
            <h3>Total Revenue</h3>
            <div class="amount">124,500.00</div>
            <p class="desc">+12.5%</p>
          </div>
          <button class="action-btn">Push to View</button>
        </div>
      </div>

      <!-- 20. Fluent UI / Acrylic -->
      <div class="demo-card card-fluent">
        <div class="card-tag">20. 亚克力 (Fluent Acrylic)</div>
        <div class="card-content">
          <h3>Total Revenue</h3>
          <div class="amount">¥ 124,500.00</div>
          <p class="desc">+12.5% from last month</p>
          <button class="action-btn">View Details</button>
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
/* Base Layout */
.demos-container {
  padding: 40px;
  min-height: 100vh;
  background-color: #eef2f6;
  background-image: radial-gradient(#d5dce6 1px, transparent 1px);
  background-size: 20px 20px;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  color: #333;
}
.demos-header {
  text-align: center;
  margin-bottom: 50px;
}
.demos-header h1 { font-size: 2.5rem; margin-bottom: 10px; color: #1a1a1a; }
.demos-header p { color: #555; margin-bottom: 20px; font-size: 1.1rem; }
.demos-grid { display: flex; flex-wrap: wrap; gap: 40px; justify-content: center; margin-top: 40px;}

.demo-card {
  width: 320px;
  height: 220px;
  position: relative;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}
.card-tag {
  position: absolute; top: -30px; left: 0; font-size: 13px; font-weight: 600; color: #555;
  background: rgba(255,255,255,0.7); padding: 2px 8px; border-radius: 4px; border: 1px solid #ddd;
  z-index: 10;
}
.tag-dark { color: #111; border-color: #999; }

/* 11. Apple / Cupertino */
.card-apple {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-radius: 20px;
  padding: 24px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.04);
  border: 1px solid rgba(255,255,255,0.8);
}
.card-apple h3 { margin: 0; font-size: 13px; color: #86868b; font-weight: 600; }
.card-apple .amount { font-size: 28px; font-weight: 600; margin: 15px 0 5px; color: #1d1d1f; letter-spacing: -0.5px; }
.card-apple .desc { font-size: 13px; color: #34c759; margin-bottom: 20px; font-weight: 500; }
.card-apple .action-btn { 
  background: #0071e3; border: none; border-radius: 14px; color: #fff;
  padding: 8px 16px; font-size: 13px; font-weight: 600; cursor: pointer;
}
.card-apple .action-btn:hover { background: #0077ed; }

/* 12. Web3 / Crypto */
.card-web3 {
  background: linear-gradient(180deg, #13131a 0%, #0a0a0f 100%);
  border-radius: 16px;
  padding: 24px;
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: 0 10px 40px rgba(138, 43, 226, 0.15), inset 0 1px 0 rgba(255,255,255,0.1);
  position: relative; overflow: hidden;
}
.card-web3::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 100%;
  background: radial-gradient(circle at 50% 0%, rgba(138,43,226,0.3) 0%, transparent 70%); pointer-events: none;
}
.card-web3 h3 { margin: 0; font-size: 12px; color: #8f929e; font-weight: 600; letter-spacing: 1px; }
.card-web3 .amount { font-size: 28px; font-weight: 800; margin: 15px 0 5px; color: #fff; background: linear-gradient(90deg, #fff, #a5b4fc); -webkit-background-clip: text; color: transparent; }
.card-web3 .desc { font-size: 12px; color: #10b981; margin-bottom: 20px; font-weight: 700; letter-spacing: 0.5px;}
.card-web3 .action-btn { 
  background: linear-gradient(90deg, #8a2be2, #4169e1); border: none; border-radius: 8px; color: #fff;
  padding: 10px 16px; font-size: 12px; font-weight: 800; cursor: pointer; width: 100%; transition: 0.3s;
}
.card-web3 .action-btn:hover { filter: brightness(1.2); box-shadow: 0 0 15px rgba(138, 43, 226, 0.5);}

/* 13. Claymorphism */
.card-clay {
  background: #f1f5f9;
  border-radius: 32px;
  padding: 24px;
  box-shadow: 12px 12px 24px #d8e0e8, -12px -12px 24px #ffffff,
              inset 4px 4px 10px rgba(255,255,255,0.8), inset -4px -4px 10px rgba(0,0,0,0.05);
  border: 2px solid #ffffff;
}
.card-clay h3 { margin: 0; font-size: 15px; color: #64748b; font-weight: 600; }
.card-clay .amount { font-size: 30px; font-weight: 800; margin: 12px 0 5px; color: #334155; }
.card-clay .desc { font-size: 13px; color: #475569; margin-bottom: 20px; font-weight: 600; background: #e2e8f0; display: inline-block; padding: 4px 10px; border-radius: 12px;}
.card-clay .action-btn { 
  background: #3b82f6; border: none; border-radius: 20px; color: #fff;
  padding: 10px 20px; font-size: 14px; font-weight: 700; cursor: pointer;
  box-shadow: inset 2px 2px 5px rgba(255,255,255,0.4), inset -2px -2px 5px rgba(0,0,0,0.2), 4px 4px 10px rgba(59, 130, 246, 0.4);
}
.card-clay .action-btn:active { box-shadow: inset 2px 2px 5px rgba(0,0,0,0.2), inset -2px -2px 5px rgba(255,255,255,0.4); transform: translateY(2px);}

/* 14. Swiss / B&W Brutalism */
.card-swiss {
  background: #fff;
  border: 3px solid #000;
  padding: 0;
  border-radius: 0;
  display: flex; flex-direction: column;
}
.card-swiss .pt { padding: 20px; flex: 1; display: flex; flex-direction: column;}
.card-swiss .swiss-title { margin: 0; border-bottom: 3px solid #000; padding-bottom: 10px; font-size: 14px; font-weight: 900; text-transform: uppercase; letter-spacing: -0.5px;}
.card-swiss .amount { font-size: 42px; font-weight: 900; margin: 15px 0 0px; color: #000; line-height: 1; letter-spacing: -2px;}
.card-swiss .desc { font-size: 14px; color: #000; font-weight: 700; margin-bottom: auto;}
.card-swiss .bottom-action { border-top: 3px solid #000; }
.card-swiss .action-btn { 
  background: #000; border: none; color: #fff; width: 100%; text-align: left;
  padding: 12px 20px; font-size: 14px; font-weight: 900; cursor: pointer; display: flex; justify-content: space-between;
}
.card-swiss .action-btn:hover { background: #fff; color: #000; outline: 3px solid #000; outline-offset: -3px;}

/* 15. Aurora / Ambient Glow */
.card-aurora {
  background: #0f172a;
  border-radius: 24px;
  padding: 24px;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0,0,0,0.2);
  border: 1px solid rgba(255,255,255,0.05);
}
.card-aurora .glow { position: absolute; border-radius: 50%; filter: blur(40px); opacity: 0.6; }
.card-aurora .g1 { width: 150px; height: 150px; background: #38bdf8; top: -50px; right: -50px; }
.card-aurora .g2 { width: 150px; height: 150px; background: #818cf8; bottom: -50px; left: -20px; }
.card-aurora .relative-z { position: relative; z-index: 2; color: #fff;}
.card-aurora h3 { margin: 0; font-size: 14px; color: rgba(255,255,255,0.6); font-weight: 500; }
.card-aurora .amount { font-size: 32px; font-weight: 300; margin: 10px 0 5px; color: #fff; }
.card-aurora .desc { font-size: 13px; color: #34d399; margin-bottom: 25px; }
.card-aurora .action-btn { 
  background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); border-radius: 12px; color: #fff; backdrop-filter: blur(10px);
  padding: 10px 20px; font-size: 13px; font-weight: 500; cursor: pointer; transition: 0.3s;
}
.card-aurora .action-btn:hover { background: rgba(255,255,255,0.2); }

/* 16. Holographic / Iridescent */
.card-holo {
  background: linear-gradient(124deg, #ff2400, #e81d1d, #e8b71d, #e3e81d, #1de840, #1ddde8, #2b1de8, #dd00f3, #dd00f3);
  background-size: 1800% 1800%;
  animation: rainbow 18s ease infinite;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 10px 30px rgba(221, 0, 243, 0.3);
  color: #fff;
}
@keyframes rainbow { 
    0%{background-position:0% 82%} 50%{background-position:100% 19%} 100%{background-position:0% 82%}
}
.card-holo h3 { margin: 0; font-size: 14px; text-shadow: 0 1px 2px rgba(0,0,0,0.3); font-weight: 600; color: rgba(255,255,255,0.9); }
.card-holo .amount { font-size: 32px; font-weight: 800; margin: 10px 0 5px; text-shadow: 0 2px 4px rgba(0,0,0,0.4); }
.card-holo .desc { font-size: 13px; margin-bottom: 20px; font-weight: 600; text-shadow: 0 1px 2px rgba(0,0,0,0.3); }
.card-holo .action-btn { 
  background: rgba(255,255,255,0.2); border: 2px solid rgba(255,255,255,0.6); border-radius: 30px; color: #fff; font-weight: bold;
  padding: 10px 20px; cursor: pointer; backdrop-filter: blur(5px); transition: 0.3s;
}
.card-holo .action-btn:hover { background: #fff; color: #333; }

/* 17. Memphis Design */
.card-memphis {
  background: #fff;
  border: 4px solid #000;
  border-radius: 0;
  padding: 24px;
  box-shadow: 8px 8px 0px #ff0055, 16px 16px 0px #00e5ff;
  background-image: radial-gradient(#000 2px, transparent 2px);
  background-size: 20px 20px;
  position: relative;
}
.card-memphis .card-content { background: #fff; padding: 10px; border: 3px solid #000; position: relative; z-index: 2; height: 100%; box-sizing: border-box; }
.card-memphis h3 { margin: 0; font-size: 16px; color: #000; font-weight: 900; background: #fff200; display: inline-block; padding: 2px 5px; border: 2px solid #000;}
.card-memphis .amount { font-size: 28px; font-weight: 900; margin: 15px 0 5px; color: #000; }
.card-memphis .desc { font-size: 14px; color: #000; margin-bottom: 10px; font-weight: 900; text-decoration: underline; text-decoration-color: #00e5ff; text-decoration-thickness: 3px;}
.card-memphis .action-btn { 
  background: #ff0055; border: 3px solid #000; color: #fff; font-weight: 900; font-size: 16px;
  padding: 8px 20px; cursor: pointer; box-shadow: 4px 4px 0px #000; transition: 0.1s; position: absolute; bottom: 10px; right: 10px;
}
.card-memphis .action-btn:active { transform: translate(4px, 4px); box-shadow: 0 0 0 #000; }

/* 18. Outline / Wireframe */
.card-outline {
  background: transparent;
  border: 2px dashed #3b82f6;
  border-radius: 8px;
  padding: 24px;
  font-family: 'Courier New', Courier, monospace;
}
.card-outline h3 { margin: 0; font-size: 14px; color: #3b82f6; font-weight: 600; text-transform: uppercase; }
.card-outline .amount { font-size: 28px; font-weight: bold; margin: 15px 0 5px; color: #1e3a8a; }
.card-outline .desc { font-size: 12px; color: #2563eb; margin-bottom: 25px; }
.card-outline .action-btn { 
  background: transparent; border: 2px solid #3b82f6; border-radius: 4px; color: #3b82f6; font-weight: bold;
  padding: 8px 16px; cursor: pointer; transition: 0.2s; font-family: 'Courier New', Courier, monospace;
}
.card-outline .action-btn:hover { background: #eff6ff; }

/* 19. Skeuomorphism */
.card-skeuo {
  background: linear-gradient(to bottom, #f0f0f0, #d4d4d4);
  border: 1px solid #a0a0a0;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 10px 20px rgba(0,0,0,0.3), inset 0 2px 3px rgba(255,255,255,0.8);
}
.card-skeuo .inner-screen {
  background: #e6ebec; border: 2px solid #b5bdbe; border-radius: 6px; padding: 15px; margin-bottom: 15px;
  box-shadow: inset 0 3px 6px rgba(0,0,0,0.15), 0 1px 0 rgba(255,255,255,0.8);
}
.card-skeuo h3 { margin: 0; font-size: 12px; color: #5a6b6d; font-weight: bold; text-shadow: 0 1px 0 rgba(255,255,255,0.5); text-transform: uppercase; }
.card-skeuo .amount { font-size: 32px; font-family: 'Courier New', Courier, monospace; font-weight: bold; margin: 5px 0 0; color: #2c3e40; text-shadow: 0 1px 0 rgba(255,255,255,0.5);}
.card-skeuo .desc { font-size: 14px; color: #438746; margin: 0; font-weight: bold; }
.card-skeuo .action-btn { 
  background: linear-gradient(to bottom, #fafafa, #e0e0e0); border: 1px solid #999; border-radius: 6px; color: #333; font-weight: bold; width: 100%;
  padding: 12px; cursor: pointer; box-shadow: 0 3px 5px rgba(0,0,0,0.2), inset 0 1px 1px rgba(255,255,255,1); text-shadow: 0 1px 0 rgba(255,255,255,0.8); transition: 0.1s;
}
.card-skeuo .action-btn:active { background: #d0d0d0; box-shadow: inset 0 3px 5px rgba(0,0,0,0.2); transform: translateY(1px); }

/* 20. Fluent UI / Acrylic */
.card-fluent {
  background: rgba(255, 255, 255, 0.4);
  backdrop-filter: blur(40px) saturate(150%);
  -webkit-backdrop-filter: blur(40px) saturate(150%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.05);
}
.card-fluent h3 { margin: 0; font-size: 14px; color: #605e5c; font-weight: 600; }
.card-fluent .amount { font-size: 32px; font-weight: 400; margin: 10px 0 5px; color: #201f1e; }
.card-fluent .desc { font-size: 12px; color: #107c10; margin-bottom: 25px; font-weight: 600; }
.card-fluent .action-btn { 
  background: #0078d4; border: none; border-radius: 4px; color: #fff; font-weight: 600;
  padding: 8px 16px; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.1); transition: 0.2s;
}
.card-fluent .action-btn:hover { background: #106ebe; }
</style>
