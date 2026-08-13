function hwmCanonicalScheduleKey(revision:number,stateHash:string,battleId:string):string{
  return `${battleId}\u001f${revision}\u001f${stateHash}`;
}
