function unpackContent(element) {
    var mainContent = "";
    for (const [key, value] of Object.entries(element)) {
      if (typeof value != "object") {
        mainContent += '<b>'+ String(key) + ':</b> ' + String(value) + '<br>'
      }
      else if (String(key) != "_metadata") {
        mainContent +=  '<b>'+ String(key) + ':</b><br><p class="tab">' + unpackContent(value) + '</p>';
      }
    }
    return mainContent;
}

function createTile(element) {
  var temp = document.createElement('div');
  temp.className = "grid-item"
  // Format tile
  temp.innerHTML = '<div class="card"><div class="card-body"><h5 class="card-title">' +
                    element._metadata.tile + 
                    '</h5><p class="card-text">' + 
                    unpackContent(element) + 
                    '</p><p class="card-text"><small class="text-muted">Created by ' +
                    element._metadata.creator +
                    '</small></p></div></div>';
  document.getElementById("result").appendChild(temp);
}

function clearTiles(elementID) {
    document.getElementById("result").innerHTML = "";
}

function rearrangeTiles() {
  msnry.destroy()
  msnry = new Masonry( grid, {itemSelector: '.grid-item'});
}
