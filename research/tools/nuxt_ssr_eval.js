// 用途：解析 Nuxt SSR頁面的 window.__NUXT__ IIFE混淆序列化格式
// （單字母/雙字母變數池 (function(a,b,c...){ return {...} })(v1,v2,...)）。
// 2026-09-27 hypothesis_queue #82 驗證：用 Node eval() 直接執行該IIFE比
// 手寫JS物件字面量解析器更穩健，可正確還原含中文的完整物件。
// 用法：node nuxt_ssr_eval.js <輸入.js，即window.__NUXT__=之後、</script>
// 之前的原始文字> <輸出.json>
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf-8');
const result = eval(src);
fs.writeFileSync(process.argv[3], JSON.stringify(result));
console.error('OK, top-level keys:', typeof result === 'object' ? Object.keys(result) : typeof result);
