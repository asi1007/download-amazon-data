class GetAdDataUseCase {
  constructor(adDataReader) {
    this.adDataReader = adDataReader;
  }

  executeLatest() {
    const latestData = this.adDataReader.fetchLatest();

    Logger.log(`最新の広告データ: ${latestData.length}件`);
    Logger.log(`対象期間: ${this.adDataReader.getLatestPeriodDate()}`);

    for (const data of latestData.slice(0, 5)) {
      Logger.log(`ASIN: ${data.asin}, 広告費: ${data.adSpend}, ACOS: ${data.acos}%`);
    }

    return latestData;
  }

  executeByDate(dateString) {
    const data = this.adDataReader.fetchByPeriod(dateString);
    Logger.log(`${dateString}の広告データ: ${data.length}件`);
    return data;
  }
}
