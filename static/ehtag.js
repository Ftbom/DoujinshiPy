class TrieNode {
    constructor() {
        this.children = {};
        this.isEndOfWord = false;
        this.data = new Set();
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
        // 添加数据
        node.data.add(data);
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
        return new Set(results);
    }
}

const dbManager = {
    db: null,
    tagstore: false,
    ver: null,
    trie: new Trie(),

    async init() {
        const need_load = await this.loadEhDatabase();
        if (need_load) {
            const db = await this.initDB();
            this.tagstore = await this.loadTrieFromDB(db);
            this.db = db;
        }
    },

    async loadEhDatabase() {
        const res = await fetch("https://api.github.com/repos/EhTagTranslation/Database/releases");
        const json = await res.json();
        const version = localStorage.getItem("tagdatabase");
        if (version == json[0].tag_name) {
            return true;
        }
        this.ver = json[0].tag_name;
        const script = document.createElement("script");
        script.src = `https://github.com/EhTagTranslation/Database/releases/download/${this.ver}/db.text.js`;
        document.body.appendChild(script);
        indexedDB.deleteDatabase('TagDatabase').onsuccess = () => {
            console.log("delete old database");
        };
        return false;
    },

    async storeDatas(tagdata) {
        const db = await this.initDB();
        const data_str = [];
        const tags = [];
        for (let i = 1; i < 12; i++) {
            for (let key of Object.keys(tagdata.data[i].data)) {
                const value = tagdata.data[i].data[key].name;
                const str = key + value;
                if (data_str.includes(str)) {
                    continue;
                }
                data_str.push(str);
                tags.push({key: key, value: value});
            }
        }
        await this.addDatas(db, tags);
        this.db = db;
        localStorage.setItem("tagdatabase", this.ver);
        this.tagstore = true;
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

    async addDatas(db, datas) {
        return new Promise((resolve, reject) => {
            const transaction = db.transaction(['myObjectStore'], 'readwrite');
            const objectStore = transaction.objectStore('myObjectStore');
            transaction.onerror = (event) => {
                console.error('Error during transaction:', event.target.error);
                reject(event.target.error);
            };
            const promises = [];
            let index = 1;
            for (let item of datas) {
                const request = objectStore.put(item);
                this.trie.insert(item.key, index);
                this.trie.insert(item.value, index);
                index++;
                promises.push(new Promise((resolve, reject) => {
                    request.onsuccess = () => resolve();
                    request.onerror = (event) => {
                        console.error(`Error adding data for key "${key}":`, event.target.error);
                        reject(event.target.error);
                    };
                }));
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
                    this.trie.insert(data.key, data.id);
                    this.trie.insert(data.value, data.id);
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
        const ids = this.trie.search(prefix);
        const results = await this.getDataByIds(Array.from(ids));
        return results.map(data => (data != null) ? [data.value, data.key] : null);
    }
};

function load_ehtagtranslation_db_text(data) {
    dbManager.storeDatas(data);
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