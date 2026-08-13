import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import vm from "node:vm";

const source=await readFile(new URL("../dist/schedule_identity.js",import.meta.url),"utf8");
const context=vm.createContext({});
vm.runInContext(source,context,{filename:"schedule_identity.js"});
const key=context.hwmCanonicalScheduleKey;
const createGuard=context.hwmCreateScheduleGuard;
assert.equal(typeof key,"function");
assert.equal(typeof createGuard,"function");

const stateA=key(1,"hash-a","battle-a");
assert.equal(stateA,key(1,"hash-a","battle-a"));
assert.notEqual(stateA,key(2,"hash-a","battle-a"));
assert.notEqual(stateA,key(1,"hash-b","battle-a"));
assert.notEqual(stateA,key(1,"hash-a","battle-b"));

const guard=createGuard();
assert.equal(guard.claim(stateA),true);
assert.equal(guard.claim(stateA),false,"duplicate canonical state must be suppressed while claimed");
const stateB=key(1,"hash-b","battle-a");
assert.equal(guard.claim(stateB),true,"same numeric revision with a new canonical hash must replan");
guard.release(stateA);
assert.equal(guard.claim(stateB),false,"an obsolete failure must not release the newer canonical state");
guard.release(stateB);
assert.equal(guard.claim(stateB),true,"a failed recommendation must release its state for reconnect retry");
guard.reset();
assert.equal(guard.claim(stateB),true,"auth/daemon lifecycle reset must permit the same canonical state again");
console.log("extension schedule identity + retry guard contract: PASS");
