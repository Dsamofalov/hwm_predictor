type HwmScheduleGuard={
  claim:(key:string)=>boolean;
  release:(key:string)=>void;
  reset:()=>void;
  current:()=>string;
};

function hwmCanonicalScheduleKey(revision:number,stateHash:string,battleId:string):string{
  return `${battleId}\u001f${revision}\u001f${stateHash}`;
}

function hwmCreateScheduleGuard():HwmScheduleGuard{
  let claimedKey="";
  return {
    claim(key:string):boolean{
      if(!key)return true;
      if(key===claimedKey)return false;
      claimedKey=key;
      return true;
    },
    release(key:string):void{
      if(key&&key===claimedKey)claimedKey="";
    },
    reset():void{
      claimedKey="";
    },
    current():string{
      return claimedKey;
    },
  };
}
