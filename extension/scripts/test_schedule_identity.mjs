import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import vm from "node:vm";

const source=await readFile(new URL("../dist/schedule_identity.js",import.meta.url),"utf8");
const context=vm.createContext({});
vm.runInContext(source,context,{filename:"schedule_identity.js"});
const key=context.hwmCanonicalScheduleKey;
assert.equal(typeof key,"function");
const baseline=key(1,"hash-a","battle-a");
assert.equal(baseline,key(1,"hash-a","battle-a"));
assert.notEqual(baseline,key(2,"hash-a","battle-a"));
assert.notEqual(baseline,key(1,"hash-b","battle-a"));
assert.notEqual(baseline,key(1,"hash-a","battle-b"));
console.log("extension schedule identity contract: PASS");
