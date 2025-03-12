class TrieNode {
    constructor() {
        this.children = {};
        this.isEndOfWord = false;
        this.data = [];
    }
}

class Trie {
    constructor() {
        this.root = new TrieNode();
    }
    insert(key, data) {
        let node = this.root;
        for (let char of key) {
            if (!node.children[char]) {
                node.children[char] = new TrieNode();
            }
            node = node.children[char];
        }
        node.isEndOfWord = true;
        // 检查数据是否已经存在
        if (!node.data.some(d => d.key === data.key && d.type === data.type)) {
            node.data.push(data);
        }
    }
    search(prefix) {
        let node = this.root;
        for (let char of prefix) {
            if (!node.children[char]) {
                return [];
            }
            node = node.children[char];
        }
        return this.collectAllWords(node);
    }
    collectAllWords(node) {
        let results = [];
        if (node.isEndOfWord) {
            results.push(...node.data);
        }
        for (let child in node.children) {
            results.push(...this.collectAllWords(node.children[child]));
        }
        return results;
    }
}

const dbManager = {
    tagstore: false,
    trie: new Trie(),

    async init() {
        const need_loaded = await this.loadEhTag();
        if (need_loaded) {
            const db = await this.initDB();
            this.tagstore = await this.loadTrieFromDB(db);
            db.close();
        }
    },

    async loadEhTag() {
        const version = localStorage.getItem("tagdatabase");
        const token = localStorage.getItem("token");
        const res = await fetch("/ehtags", { headers: { Authorization: "Bearer " + token } });
        if (res.status == 400) {
            return false;
        }
        const info = await res.json();
        if (version == info.version) {
            return true;
        }
        indexedDB.deleteDatabase('TagDatabase').onsuccess = () => {
            console.log("delete old db");
        };
        const file = await fetch(info.url, { headers: { Authorization: "Bearer " + token } });
        const tags = await file.json();
        const db = await this.initDB();
        await this.addDatas(db, tags);
        db.close();
        localStorage.setItem("tagdatabase", info.version);
        this.tagstore = true;
        return false;
    },

    initDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open('TagDatabase', 1);
            request.onupgradeneeded = function (event) {
                const db = event.target.result;
                if (!db.objectStoreNames.contains('myObjectStore')) {
                    const objectStore = db.createObjectStore('myObjectStore', { keyPath: 'id', autoIncrement: true });
                    objectStore.createIndex('keyIndex', 'key', { unique: false });
                    objectStore.createIndex('valueIndex', 'value', { unique: false });
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

    async addDatas(db, datas) {
        return new Promise((resolve, reject) => {
            const transaction = db.transaction(['myObjectStore'], 'readwrite');
            const objectStore = transaction.objectStore('myObjectStore');
            transaction.onerror = (event) => {
                console.error('Error during transaction:', event.target.error);
                reject(event.target.error);
            };
            const promises = [];
            for (let category of Object.keys(datas)) {
                for (let key of Object.keys(datas[category])) {
                    const data = { key: key, value: datas[category][key], type: category };
                    const request = objectStore.add(data);
                    this.trie.insert(data.key, data);
                    this.trie.insert(data.value, data);
                    promises.push(new Promise((resolve, reject) => {
                        request.onsuccess = () => resolve();
                        request.onerror = (event) => {
                            console.error(`Error adding data for key "${key}":`, event.target.error);
                            reject(event.target.error);
                        };
                    }));
                }
            }
            Promise.all(promises).then(() => {
                console.log('Transaction completed successfully');
                resolve();
            }).catch((error) => {
                console.error('Error adding data:', error);
                reject(error);
            });
        });
    },

    async loadTrieFromDB(db) {
        return new Promise((resolve, reject) => {
            const transaction = db.transaction(['myObjectStore'], 'readonly');
            const objectStore = transaction.objectStore('myObjectStore');
            const request = objectStore.openCursor();
            request.onsuccess = (event) => {
                const cursor = event.target.result;
                if (cursor) {
                    const data = cursor.value;
                    this.trie.insert(data.key, data);
                    this.trie.insert(data.value, data);
                    cursor.continue();
                } else {
                    console.log('Loaded trie from DB');
                    resolve(true);
                }
            };
            request.onerror = (event) => {
                console.error('Error loading trie from DB:', event.target.error);
                reject(false);
            };
        });
    },

    search(prefix) {
        if (!this.tagstore) {
            return [];
        }
        const results = this.trie.search(prefix);
        return results.map(data => [data.value, `${data.type}:${data.key}`]);
    }
};

const searchInput = document.getElementById("search");
const suggestions = document.getElementById("suggestions");
let isMouseOverSuggestions = false;

// 监听 suggestions 的鼠标进入和离开
suggestions.addEventListener("mouseenter", function () {
    isMouseOverSuggestions = true;
});

suggestions.addEventListener("mouseleave", function () {
    isMouseOverSuggestions = false;
});

// 监听 input 失去焦点
searchInput.addEventListener("blur", function () {
    setTimeout(() => {
        if (!isMouseOverSuggestions) {
            suggestions.innerHTML = "";
        }
    }, 200);
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

function showSuggestions(query) {
    const suggestions = dbManager.search(query);
    let suggestionsHtml = "";
    for (let suggestion of suggestions) {
        suggestionsHtml += `<a href="#" class="list-group-item list-group-item-action" onclick="selectSuggestion('${suggestion[1]}')">
            <div>${suggestion[0]}</div>
            <small class="text-muted">${suggestion[1]}</small>
        </a>`;
    }
    document.getElementById("suggestions").innerHTML = suggestionsHtml;
}

function selectSuggestion(suggestion) {
    const query = document.getElementById("search");
    const arr = query.value.split("$,").map(str => str.trim()).filter(str => str !== "");
    arr.pop();
    arr.push(suggestion);
    setTimeout(() => {
        query.value = arr.join("$, ");
        query.focus();
        document.getElementById("suggestions").innerHTML = "";
    }, 200);
}

// 初始化数据库和标签存储
dbManager.init();
