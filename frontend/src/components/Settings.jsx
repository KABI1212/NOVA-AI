function Settings() {
  return (
    <div className="panel">
      <div className="panel-header">
        <h1 className="text-2xl font-semibold text-white">Settings</h1>
        <p className="text-sm text-gray-400">Personalize your NOVA AI experience.</p>
      </div>
      <div className="panel-body space-y-4">
        <div className="setting-card">
          <h2 className="text-lg text-white font-medium">Theme</h2>
          <p className="text-sm text-gray-400">Dark mode is enabled by default.</p>
        </div>
        <div className="setting-card">
          <h2 className="text-lg text-white font-medium">Streaming</h2>
          <p className="text-sm text-gray-400">
            Responses stream character-by-character to mimic ChatGPT.
          </p>
        </div>
        <div className="setting-card">
          <h2 className="text-lg text-white font-medium">Voice</h2>
          <p className="text-sm text-gray-400">
            Speech recognition and synthesis are provided by the browser.
          </p>
        </div>
      </div>
    </div>
  )
}

export default Settings
