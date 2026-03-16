/* @meta
{
  "name": "jd/shop-prices",
  "description": "读取当前页面已渲染的京东店铺商品列表及价格（分段滚动+价格补偿）",
  "domain": "mall.jd.com",
  "args": {},
  "readOnly": true,
  "example": "bb-browser site jd/shop-prices"
}
*/

async function(args) {
  // 先等价格元素有内容（最多5秒）
  for (let i = 0; i < 10; i++) {
    const filled = Array.from(document.querySelectorAll('span.jdNum')).filter(el => el.innerText.trim()).length;
    if (filled > 0) break;
    await new Promise(r => setTimeout(r, 500));
  }

  // 分段滚动，确保所有商品进入视口触发懒加载
  const totalHeight = document.body.scrollHeight;
  const steps = 10;
  for (let i = 1; i <= steps; i++) {
    window.scrollTo(0, (totalHeight / steps) * i);
    await new Promise(r => setTimeout(r, 200));
  }
  // 回到顶部，再等一下让价格全部渲染
  window.scrollTo(0, 0);
  await new Promise(r => setTimeout(r, 800));

  // 读取商品列表
  const items = [];
  document.querySelectorAll('li.jSubObject').forEach(li => {
    const priceEl = li.querySelector('span.jdNum');
    if (!priceEl) return;
    const skuId = priceEl.getAttribute('jdprice') || '';
    if (!skuId) return;
    const price = priceEl.innerText.trim().replace(/[^0-9.]/g, '') || null;
    const prePrice = (priceEl.getAttribute('preprice') || '').replace(/[^0-9.]/g, '') || null;
    const descEl = li.querySelector('.jDesc a');
    const name = descEl ? descEl.innerText.trim() : '';
    const linkEl = li.querySelector('a[href*="item.jd.com"]');
    const href = linkEl ? linkEl.href.split('?')[0] : `https://item.jd.com/${skuId}.html`;
    items.push({ skuId, name, price, originalPrice: prePrice, href });
  });

  if (items.length === 0) {
    return { error: '未找到商品', url: location.href, title: document.title };
  }

  // 找出价格为空的 SKU，用 p.3.cn 补查
  const missingSkus = items.filter(i => !i.price).map(i => i.skuId);
  if (missingSkus.length > 0) {
    const priceMap = await new Promise(resolve => {
      const map = {};
      const skuParam = missingSkus.map(id => 'J_' + id).join(',');
      const xhr = new XMLHttpRequest();
      xhr.open('GET', `https://p.3.cn/prices/mgets?skuIds=${skuParam}&type=1&area=1_72_2799_0`, true);
      xhr.timeout = 8000;
      xhr.onload = () => {
        try {
          JSON.parse(xhr.responseText).forEach(item => {
            map[item.id.replace('J_', '')] = { price: item.p, originalPrice: item.op || item.m };
          });
        } catch(e) {}
        resolve(map);
      };
      xhr.onerror = xhr.ontimeout = () => resolve(map);
      xhr.send();
    });

    items.forEach(item => {
      if (!item.price && priceMap[item.skuId]) {
        item.price = priceMap[item.skuId].price || null;
        item.originalPrice = item.originalPrice || priceMap[item.skuId].originalPrice || null;
        item.priceSource = 'api';
      }
    });
  }

  // 找下一页链接
  const nextLink = Array.from(document.querySelectorAll('a')).find(a => a.innerText.trim() === '下一页');
  const nextUrl = nextLink ? nextLink.href : null;

  const withPrice = items.filter(i => i.price).length;
  return {
    url: location.href,
    count: items.length,
    withPrice,
    missingCount: items.length - withPrice,
    nextUrl,
    items
  };
}
