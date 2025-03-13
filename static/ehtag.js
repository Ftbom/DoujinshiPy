class SearchEngine {
    constructor(n = 2) {
        this.index = new Map();
        this.n = n; // N-gram 窗口大小
    }

    // 添加数据
    addData(id, value, key) {
        this._indexData(id, value);
        this._indexData(id, key);
    }

    // 构建索引
    _indexData(id, text) {
        const grams = this._generateNgrams(text);
        for (const gram of grams) {
            if (!this.index.has(gram)) {
                this.index.set(gram, new Set());
            }
            this.index.get(gram).add(id);
        }
    }

    // 生成 N-gram
    _generateNgrams(text) {
        text = text.toLowerCase();
        const grams = new Set();
        for (let i = 0; i <= text.length - this.n; i++) {
            grams.add(text.substring(i, i + this.n));
        }
        return grams;
    }

    // 模糊查询
    search(query) {
        query = query.toLowerCase();
        const grams = this._generateNgrams(query);
        let resultSet = new Set();

        for (const gram of grams) {
            if (this.index.has(gram)) {
                if (resultSet.size === 0) {
                    resultSet = new Set(this.index.get(gram));
                } else {
                    resultSet = new Set([...resultSet].filter(id => this.index.get(gram).has(id)));
                }
            }
        }
        return [...resultSet];
    }
}

function needUpdate() {
    const savedTime = localStorage.getItem("lastupdate");
    if (!savedTime) {
        return true; // 没有记录，默认认为已过期
    }
    const savedDate = new Date(parseInt(savedTime, 10)); // 转换为日期对象
    const now = new Date();
    // 计算 savedDate + 1 个月的日期
    const oneMonthLater = new Date(savedDate);
    oneMonthLater.setMonth(savedDate.getMonth() + 1);
    return now >= oneMonthLater; // 如果当前时间大于等于 oneMonthLater，则超过 1 个月
}

const dbManager = {
    db: null,
    tagstore: false,
    engine: new SearchEngine(),

    async init() {
        const need_load = await this.loadEhDatabase();
        if (need_load) {
            const db = await this.initDB();
            this.tagstore = await this.loadEngineFromDB(db);
            this.db = db;
        }
    },

    async loadEhDatabase() {
        if (!needUpdate()) {
            return true;
        }
        // 加载中
        const loading = document.createElement("div");
        loading.innerHTML = `<div id="loading-mask">
            <div class="spinner"></div>
                <p>更新EHTag数据库...</p>
            </div>`;
        document.body.appendChild(loading);
        // 删除旧数据
        indexedDB.deleteDatabase('TagDatabase').onsuccess = () => {
            console.log("delete old database");
        };
        // 获取新数据
        const script = document.createElement("script");
        script.src = "https://github.com/EhTagTranslation/Database/releases/latest/download/db.text.js";
        document.body.appendChild(script);
        return false;
    },

    initDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open('TagDatabase', 1);
            request.onupgradeneeded = function (event) {
                const db = event.target.result;
                if (!db.objectStoreNames.contains('myObjectStore')) {
                    db.createObjectStore('myObjectStore', { keyPath: 'id', autoIncrement: true });
                }
            };
            request.onsuccess = function (event) {
                const db = event.target.result;
                resolve(db);
            };
            request.onerror = function (event) {
                console.error('Database error: ', event.target.errorCode);
                reject(event.target.error);
            };
        });
    },

    async addDatas(tagdata) {
        const db = await this.initDB();
        return new Promise((resolve, reject) => {
            const data_str = [];
            const transaction = db.transaction(['myObjectStore'], 'readwrite');
            const objectStore = transaction.objectStore('myObjectStore');
            transaction.onerror = (event) => {
                console.error('Error during transaction:', event.target.error);
                reject(event.target.error);
            };
            const promises = [];
            let index = 1;
            for (let i = 1; i < 12; i++) {
                for (let key of Object.keys(tagdata.data[i].data)) {
                    const value = tagdata.data[i].data[key].name;
                    const str = key + value;
                    if (data_str.includes(str)) {
                        continue;
                    }
                    data_str.push(str);
                    const item = { key: key, value: value };
                    const request = objectStore.put(item);
                    this.engine.addData(index, item.value, item.key);
                    index++;
                    promises.push(new Promise((resolve, reject) => {
                        request.onsuccess = () => resolve();
                        request.onerror = (event) => {
                            console.error(`Error adding data for key "${key}":`, event.target.error);
                            reject(event.target.error);
                        };
                    }));
                }
            }
            this.db = db;
            // 记录更新时间
            localStorage.setItem("lastupdate", Date.now());
            this.tagstore = true;
            // 加载中消失
            document.getElementById("loading-mask").style.display = "none";
            Promise.all(promises).then(() => {
                console.log('Transaction completed successfully');
                resolve();
            }).catch((error) => {
                console.error('Error adding data:', error);
                reject(error);
            });
        });
    },

    async loadEngineFromDB(db) {
        return new Promise((resolve, reject) => {
            const transaction = db.transaction(['myObjectStore'], 'readonly');
            const objectStore = transaction.objectStore('myObjectStore');
            const request = objectStore.openCursor();
            request.onsuccess = (event) => {
                const cursor = event.target.result;
                if (cursor) {
                    const data = cursor.value;
                    this.engine.addData(data.id, data.value, data.key);
                    cursor.continue();
                } else {
                    console.log('Loaded data from DB');
                    resolve(true);
                }
            };
            request.onerror = (event) => {
                console.error('Error loading data from DB:', event.target.error);
                reject(false);
            };
        });
    },

    async getDataByIds(idList) {
        return Promise.all(idList.map(id => {
            return new Promise((resolve, reject) => {
                const transaction = this.db.transaction(["myObjectStore"], "readonly");
                const objectStore = transaction.objectStore("myObjectStore");
                const request = objectStore.get(id);
                request.onsuccess = function () {
                    resolve(request.result || null); // 如果找不到数据，返回 null
                };
                request.onerror = function () {
                    reject(`Error fetching data for id: ${id}`);
                };
            });
        }));
    },

    async search(prefix) {
        if (!this.tagstore) {
            return [];
        }
        const ids = this.engine.search(prefix);
        const results = await this.getDataByIds(Array.from(ids));
        return results.map(data => (data != null) ? [data.value, data.key] : null);
    }
};

function load_ehtagtranslation_db_text(data) {
    dbManager.addDatas(data);
}

let isMouseOverSuggestions = false;

// 监听 input 失去焦点
document.getElementById("search").addEventListener("blur", function () {
    setTimeout(() => {
        if (!isMouseOverSuggestions) {
            document.getElementById("suggestions").innerHTML = "";
        }
    }, 500);
});

function handleSuggestions(event) {
    if (event.key === "Enter") {
        event.preventDefault();
        const query = document.getElementById("search");
        document.getElementById("suggestions").style.width = query.clientWidth + "px";
        const arr = query.value.split("$,").map(str => str.trim()).filter(str => str !== "");
        showSuggestions(arr[arr.length - 1]);
    } else if (event.key === "Escape") {
        document.getElementById("suggestions").innerHTML = "";
    }
}

function selectSuggestionItem(suggestion) {
    isMouseOverSuggestions = true;
    const query = document.getElementById("search");
    const arr = query.value.split("$,").map(str => str.trim()).filter(str => str !== "");
    arr.pop();
    arr.push(suggestion);
    setTimeout(() => {
        query.value = arr.join("$, ");
        query.focus();
        document.getElementById("suggestions").innerHTML = "";
        isMouseOverSuggestions = false;
    }, 200);
}

async function showSuggestions(query) {
    const suggestions = await dbManager.search(query);
    let suggestionsHtml = "";
    for (let suggestion of suggestions) {
        if (suggestion == null) {
            continue;
        }
        suggestionsHtml += `<a class="list-group-item list-group-item-action" onclick="selectSuggestionItem('${suggestion[1]}')">
            <div>${suggestion[0]}</div>
            <small class="text-muted">${suggestion[1]}</small>
        </a>`;
    }
    document.getElementById("suggestions").innerHTML = suggestionsHtml;
}

// 初始化数据库和标签存储
dbManager.init();