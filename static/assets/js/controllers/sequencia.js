angular.module('deciframeApp').controller('SequenciaController', function($http, $window, ngProgressFactory, $anchorScroll, $location, GENEROS) {
  var COR_SEQUENCIA = '#2E1C74';
  var vm = this;

  vm.sequenciasFamosas = [];
  vm.minhaSequencia = {};
  vm.isSearching = false;
  vm.showSearchResultsCount = false;
  vm.esfigeSpeech =  "";
  vm.musics = [];
  vm.generos = GENEROS;
  vm.meuGenero = "";
  vm.progressbar = ngProgressFactory.createInstance();

  vm.novaSequencia = { nome: '', acordesTexto: '' };
  vm.cadastrando = false;
  vm.mensagemCadastro = '';
  vm.cadastroSemResultados = false;
  vm.erroCadastro = '';
  vm.erroCatalogo = '';

  var formatarSequencia = function(sequencia) {
    return {
      id: sequencia.id,
      nome: sequencia.nome,
      is_builtin: sequencia.is_builtin,
      acordes: (sequencia.acordes || []).map(function(acorde) {
        return { 'acorde': acorde, 'cor': COR_SEQUENCIA };
      })
    };
  };

  vm.carregarSequencias = function() {
    vm.erroCatalogo = '';
    $http.get('sequencias')
      .success(function(data) {
        vm.sequenciasFamosas = (data || []).map(formatarSequencia);
      })
      .error(function() {
        vm.erroCatalogo = 'Não foi possível carregar o catálogo de sequências.';
      });
  };

  vm.cadastrarSequencia = function() {
    vm.mensagemCadastro = '';
    vm.cadastroSemResultados = false;
    vm.erroCadastro = '';

    var nome = (vm.novaSequencia.nome || '').trim();
    var acordes = (vm.novaSequencia.acordesTexto || '')
      .split(',')
      .map(function(acorde) { return acorde.trim(); })
      .filter(function(acorde) { return acorde.length > 0; });

    if (!nome || !acordes.length) {
      vm.erroCadastro = 'Informe um nome e pelo menos um acorde.';
      return;
    }

    vm.cadastrando = true;
    $http.post('sequencias', { nome: nome, acordes: acordes })
      .success(function(data) {
        vm.cadastrando = false;
        vm.sequenciasFamosas.push(formatarSequencia(data));
        vm.cadastroSemResultados = (data.total_musicas === 0);

        if (vm.cadastroSemResultados) {
          vm.mensagemCadastro = 'Sequência cadastrada, mas nenhuma música foi encontrada com ela hoje.';
        } else {
          vm.mensagemCadastro = 'Sequência cadastrada. Ela retorna ' +
            data.total_musicas + ' música(s) hoje.';
        }

        vm.novaSequencia = { nome: '', acordesTexto: '' };
      })
      .error(function(data, status) {
        vm.cadastrando = false;
        if (data && data.erro) {
          vm.erroCadastro = data.erro;
        } else if (status === 409) {
          vm.erroCadastro = 'Essa sequência já está cadastrada.';
        } else {
          vm.erroCadastro = 'Não foi possível cadastrar a sequência.';
        }
      });
  };

  vm.temAcorde = function(acorde) {
    if (vm.minhaSequencia.acordes) {
      return (vm.minhaSequencia.acordes.indexOf(acorde) > -1);
    } else {
      return false;
    }
  }

  var createChordsString = function(chords) {
    var str = "";
    for (var i = 0; i < chords.length; i++) {
      str = str.concat(chords[i].acorde, ',');
    }
    return str.substring(0, str.length-1);
  }

  vm.pesquisarPorSequencia = function(sequencia) {
    if (sequencia) {
      vm.minhaSequencia = sequencia;
    }
    vm.progressbar.start();
    vm.esfigeSpeech = "Procurando músicas com base na sequencia...";
    vm.isSearching = true;
    vm.musics = [];

    var apiUrl = "";
    var searchString = "similares?sequencia=".concat(createChordsString(vm.minhaSequencia.acordes));
    if (vm.meuGenero !== "" && vm.meuGenero !== null) {
      searchString += "&generos="+vm.meuGenero;
    }
    $http.get(apiUrl.concat(searchString))
      .success(function(data) {
        vm.progressbar.complete();
        vm.esfigeSpeech = "Encontrei essas músicas";
        vm.isSearching = false;
        vm.showSearchResultsCount = true;
        vm.musics = data;
      })
      .error(function(data) {
        vm.esfigeSpeech = "Ops! Algo errado.";
        vm.isSearching = false;
        vm.showSearchResultsCount = false;
      });
  }

  vm.limparPesquisa = function() {
    vm.minhaSequencia = {};
    vm.musics = [];
  }

  vm.goToLirics = function(music) {
    $window.open(music.url);
  };

  vm.goToResults = function() {
    vm.showSearchResultsCount = false;
    $("body").animate({scrollTop: $("#results").offset().top}, "slow");
  };

  vm.carregarSequencias();
});
