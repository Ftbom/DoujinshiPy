/*
创建表：
CREATE TABLE public.doujinshis (
  id text PRIMARY KEY,
  title text NOT NULL,
  page int NOT NULL,
  time int NOT NULL
);
*/

const PAGE_SIZE = 10;
const IMAGE_BASE = '/doujinshi/$id/thumbnail';

//系统变量
let page = 0;
let loading_list = false;
let hasMore = true;
const loadImgs = [];
let loadingImg = false;
//阅读界面变量
let reader_id = null;
let reader_title = null;
let debounceTimer = null;
//配置
let config = {
    POSTGREST_URL: localStorage.getItem('POSTGREST_URL'),
    POSTGREST_API_KEY: localStorage.getItem('POSTGREST_API_KEY'),
    TABLE_NAME: localStorage.getItem('TABLE_NAME'),
};

const css_style = document.createElement('style');
const btn = document.createElement('div');
const panel = document.createElement('div');
const configPanel = document.createElement('div');

let has_loaded_history = false;
saveReadProgress();

if (showFloatingBtn()) {
    //css
    css_style.innerHTML = `
        #tm_floating_btn {
            position: fixed; right: 20px; bottom: 20px;
            width: 50px; height: 50px;
            border-radius: 50%; background: #1e90ff;
            cursor: pointer; z-index: 9999;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }
        #tm_list_panel {
            position: fixed; right: 20px; bottom: 80px;
            width: 300px; max-height: 400px;
            background: white; border: 1px solid #ccc;
            border-radius: 6px; box-shadow: 0 2px 12px rgba(0,0,0,0.2);
            overflow-y: auto; display: none;
            z-index: 9998;
        }
        #top_buttons {
            text-align: center;
            padding: 6px;
            border-bottom: 1px solid #eee;
        }
        #tm_clear_all {
            background: #ff4d4f;
            color: white;
            border: none;
            border-radius: 4px;
            width: 100px;
            cursor: pointer;
        }
        #refresh_list {
            margin-left: 8px;
            background: #1e90ff;
            color: white;
            border: none;
            border-radius: 4px;
            width: 100px;
            cursor: pointer;
        }
        .tm-list-item {
            display: flex; align-items: center;
            padding: 8px; border-bottom: 1px solid #eee;
        }
        .tm-list-item img {
            width: 50px; height: 50px;
            object-fit: cover; border-radius: 4px;
            margin-right: 8px; cursor: pointer;
        }
        .tm-list-item .title {
            flex: 1; font-size: 14px; color: #333;
            white-space: nowrap; overflow: hidden;
            text-overflow: ellipsis; margin-right: 8px;
        }
        .tm-list-item .btn-del {
            background: #ff4d4f; color: white;
            border: none; border-radius: 4px;
            padding: 4px 8px; cursor: pointer;
        }
        .tm-loading {
            text-align: center; padding: 10px; color: #888;
        }
        #tm_config_panel {
            position: fixed; right: 20px; bottom: 80px;
            width: 300px; background: #fff;
            border: 1px solid #ccc; border-radius: 8px;
            padding: 15px; z-index: 10000;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        #tm_config_panel input {
            width: 99%; margin-bottom: 10px; padding: 6px;
            font-size: 14px; border: 1px solid #ccc;
            border-radius: 4px;
        }
        #tm_config_panel button {
            width: 100%; padding: 8px; font-size: 14px;
            background: #1e90ff; color: white;
            border: none; border-radius: 4px;
            cursor: pointer;
        }
    `;
    document.body.appendChild(css_style);
    //添加悬浮按钮
    btn.id = 'tm_floating_btn';
    btn.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" style="margin:13px;">
    <path d="M12 8v5h4M12 2a10 10 0 1 0 10 10"
        stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`;
    document.body.appendChild(btn);
    //配置界面
    panel.id = 'tm_list_panel';
    document.body.appendChild(panel);
    const topBar = document.createElement('div');
    topBar.id = 'top_buttons';
    topBar.innerHTML = `<button id="tm_clear_all">删除全部</button><button id="refresh_list">刷新列表</button>`;
    panel.appendChild(topBar);
    document.getElementById('tm_clear_all').addEventListener('click', () => {
        deleteAllItems();
    });
    document.getElementById('refresh_list').addEventListener('click', () => {
        refreshList();
    });
    //列表
    configPanel.id = 'tm_config_panel';
    configPanel.style.display = 'none';
    configPanel.innerHTML = `
        <h4>
            PostgREST配置
            <i class="bi bi-info-circle-fill fs-6"
                data-bs-toggle="tooltip"
                data-bs-placement="right"
                title="PostgREST应该在同一域名下(否则需允许跨源请求)，推荐使用Supabase"
                style="cursor: pointer;"></i>
        </h4>
        <input id="tm_url" placeholder="POSTGREST_URL" value="${config.POSTGREST_URL || ''}">
        <input id="tm_key" placeholder="POSTGREST_API_KEY" value="${config.POSTGREST_API_KEY || ''}">
        <input id="tm_table" placeholder="TABLE_NAME" value="${config.TABLE_NAME || ''}">
        <button id="tm_save_btn">保存配置</button>
    `;
    document.body.appendChild(configPanel);
    //保存配置
    document.getElementById('tm_save_btn').addEventListener('click', () => {
        const url = document.getElementById('tm_url').value.trim();
        const key = document.getElementById('tm_key').value.trim();
        const table = document.getElementById('tm_table').value.trim();
        if (!url || !key || !table) {
            alert('请填写所有字段');
            return;
        }
        localStorage.setItem('POSTGREST_URL', url);
        localStorage.setItem('POSTGREST_API_KEY', key);
        localStorage.setItem('TABLE_NAME', table);
        config = {
            POSTGREST_URL: url,
            POSTGREST_API_KEY: key,
            TABLE_NAME: table
        };
        const items = panel.querySelectorAll('.tm-list-item');
        items.forEach(el => el.remove());
        configPanel.style.display = 'none';
        panel.style.display = 'block';
        loadMore(); // 自动加载数据
    });
    //显示界面
    btn.addEventListener('click', () => {
        //显示配置界面
        if (configPanel.style.display === 'block') {
            configPanel.style.display = 'none';
            return;
        }
        if (!config.POSTGREST_URL || !config.POSTGREST_API_KEY || !config.TABLE_NAME) {
            configPanel.style.display = 'block';
            return;
        }
        //显示列表
        if ((panel.style.display === 'none') || (panel.style.display === '')) {
            panel.style.display = 'block';
            if (page === 0 && panel.children.length === 1) {
                loadMore();
            }
        } else {
            panel.style.display = 'none';
        }
    });
    btn.addEventListener('contextmenu', function (e) {
        e.preventDefault(); // 阻止默认菜单
        panel.style.display = 'none';
        configPanel.style.display = 'block';
    });
    //翻页
    panel.addEventListener('scroll', () => {
        if (!loading_list && hasMore) {
            const {
                scrollTop,
                scrollHeight,
                clientHeight
            } = panel;
            if (scrollTop + clientHeight + 20 >= scrollHeight) {
                loadMore();
            }
        }
    });
}

function showFloatingBtn() {
    const path_name = window.location.pathname;
    if (path_name.startsWith("/web/read")) {
        reader_id = path_name.split("/").slice(-1)[0];
        reader_title = document.getElementById("title-header").textContent.replaceAll("\n", "").trim();
        if (reader_title.search("Doujinshi不存在") != -1) {
            return 0;
        }
        if (!config.POSTGREST_URL || !config.POSTGREST_API_KEY || !config.TABLE_NAME) {
            return 0;
        }
        //替换原loadPage函数
        const OriginloadPage = window.loadPage;
        window.loadPage = function (selected) {
            OriginloadPage(selected);
            localStorage.setItem('readProgress', `${reader_id}|$|${reader_title}|$|${selected + 1}`);
            if (debounceTimer){
                clearTimeout(debounceTimer);
            }
            debounceTimer = setTimeout(() => {
                saveReadProgress();
            }, 1500); //1.5秒后才发请求
        };
        return 0;
    }
    return 1;
}

//保存进度
async function saveReadProgress() {
    const read_progress = localStorage.getItem('readProgress');
    if (read_progress === null) {
        return;
    }
    const [id_, title_, page_] = read_progress.split("|$|");
    localStorage.removeItem('readProgress');
    await AddItemToDB(id_, title_, page_);
    if (has_loaded_history) {
        refreshList();
    }
    return;
}

//刷新列表
function refreshList() {
    const items = panel.querySelectorAll('.tm-list-item');
    items.forEach(el => el.remove());
    page = 0;
    loadImgs.length = 0;
    loadingImg = false;
    loadMore();
}

//加载更多
async function loadMore() {
    has_loaded_history = true;
    //加载中界面
    loading_list = true;
    const loader = document.createElement('div');
    loader.className = 'tm-loading';
    loader.textContent = '加载中...';
    panel.appendChild(loader);
    try {
        const offset = page * PAGE_SIZE;
        const url = `${config.POSTGREST_URL}/${config.TABLE_NAME}?select=id,title,page&order=time.desc&limit=${PAGE_SIZE}&offset=${offset}`;
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'apikey': config.POSTGREST_API_KEY,
                'Authorization': `Bearer ${config.POSTGREST_API_KEY}`,
                'Accept': 'application/json'
            }
        });
        if (response.status === 200) {
            const items = await response.json();
            appendItems(items);
            if (!loadingImg) {
                startLoadImgs();
            }
            hasMore = items.length === PAGE_SIZE;
            if (hasMore) page++;
        } else {
            console.error('加载失败', response);
            alert('加载失败');
        }
    } catch (err) {
        console.error('请求出错', err);
        alert('请求出错');
    }
    loader.remove();
    loading_list = false;
}

//添加项到界面
function appendItems(items) {
    items.forEach(item => {
        const el = document.createElement('div');
        el.className = 'tm-list-item';
        el.innerHTML = `
                <a href="/web/read/${item.id}?page=${item.page}">
                <img id="history_${item.id}" src="/web/static/loading.gif" alt="${item.title}">
                </a>
                <div class="title">${item.title}</div>
                <button class="btn-del">删除</button>
            `;
        loadImgs.unshift(item.id);
        el.querySelector('.btn-del').addEventListener('click', () => {
            deleteItemFromDB(item.id, () => el.remove());
        });
        panel.appendChild(el);
    });
}

//清空数据
async function deleteAllItems() {
    if (!confirm('确定删除所有数据？')) {
        return;
    }
    try {
        const url = `${config.POSTGREST_URL}/${config.TABLE_NAME}?id=neq.null`;
        const response = await fetch(url, {
            method: 'DELETE',
            headers: {
                'apikey': config.POSTGREST_API_KEY,
                'Authorization': `Bearer ${config.POSTGREST_API_KEY}`,
                'Prefer': 'return=minimal'
            }
        });
        if (response.status === 204) {
            const items = panel.querySelectorAll('.tm-list-item');
            items.forEach(el => el.remove());
        } else {
            console.error('清空数据库失败', response);
            alert('清空数据库失败');
        }
    } catch (err) {
        console.error('请求出错', err);
        alert('请求出错');
    }
}

//删除数据
async function deleteItemFromDB(id, callback) {
    try {
        const url = `${config.POSTGREST_URL}/${config.TABLE_NAME}?id=eq.${encodeURIComponent(id)}`;
        const response = await fetch(url, {
            method: 'DELETE',
            headers: {
                'apikey': config.POSTGREST_API_KEY,
                'Authorization': `Bearer ${config.POSTGREST_API_KEY}`,
                'Prefer': 'return=minimal'
            }
        });
        if (response.status === 204) {
            callback();
        } else {
            console.error('删除失败', response);
            alert('删除失败');
        }
    } catch (err) {
        console.error('请求失败', err);
        alert('请求失败');
    }
}

//添加数据到数据库
async function AddItemToDB(id, title, page) {
    try {
        const url = `${config.POSTGREST_URL}/${config.TABLE_NAME}?on_conflict=id`;
        const data = {
            id: id,
            title: title,
            page: parseInt(page),
            time: Math.floor(Date.now() / 1000)
        };
        const response = await fetch(url, {
            method: 'POST',
            body: JSON.stringify([data]),
            headers: {
                'apikey': config.POSTGREST_API_KEY,
                'Authorization': `Bearer ${config.POSTGREST_API_KEY}`,
                'Content-Type': 'application/json',
                'Prefer': 'resolution=merge-duplicates,return=representation'
            }
        });
        if (response.status === 201) {
            console.log('已添加');
            refreshList();
        } else if (response.status === 200) {
            console.log('已更新');
            refreshList();
        } else if (response.status != 409) {
            console.error('添加失败:', response);
            alert('添加失败');
        }
    } catch (err) {
        console.error('请求出错', err);
        alert('请求出错');
    }
}

//开始加载图片
async function startLoadImgs() {
    const token = localStorage.getItem("token");
    let id = loadImgs.pop();
    while (id != undefined) {
        const img_cover = document.getElementById(id);
        const img = document.getElementById("history_" + id);
        if (img_cover != null) {
            img.src = img_cover.src;
        } else {
            const imageBlob = await fetchImage(id, token);
            img.src = URL.createObjectURL(imageBlob); //图片数据转blob
        }
        id = loadImgs.pop();
    }
    loadingImg = false;
}

//加载图片数据
async function fetchImage(id, token) {
    try {
        const response = await fetch(IMAGE_BASE.replace("$id", id), {
            method: 'GET',
            headers: {
                Authorization: `Bearer ${token}`
            }
        });

        if (response.status === 200) {
            const blob = await response.blob(); // 获取 blob 数据
            return blob; // resolve(blob)
        } else {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

    } catch (error) {
        throw error; // reject(error)
    }
}
