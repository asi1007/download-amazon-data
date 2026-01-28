function getScriptProperty(key) {
  const value = PropertiesService.getScriptProperties().getProperty(key);
  if (!value) {
    throw new Error(`Script Property "${key}" が設定されていません。プロジェクトの設定で設定してください。`);
  }
  return value;
}

const API_KEY = getScriptProperty('API_KEY');
const API_SECRET = getScriptProperty('API_SECRET');
const REFRESH_TOKEN = getScriptProperty('REFRESH_TOKEN');

function getAuthToken() {
  const url = "https://api.amazon.com/auth/o2/token";
  const payload = {
    'grant_type': 'refresh_token',
    'refresh_token': REFRESH_TOKEN,
    'client_id': API_KEY,
    'client_secret': API_SECRET
  };
  const options = {
    method: 'post',
    payload: payload
  };
  const response = UrlFetchApp.fetch(url, options);
  const json = JSON.parse(response.getContentText());
  return json.access_token;
}
