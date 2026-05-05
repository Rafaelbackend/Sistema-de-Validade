CREATE DATABASE Estoque_Mercado;

-- Tabela de Administradores
CREATE TABLE administrador_estoque (
    id_adm SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    senha VARCHAR(255) NOT NULL -- Suporta hashes SHA-256 ou Bcrypt
);

-- Tabela de Setores (Limpeza, Alimentos, etc.)
CREATE TABLE setor (
    id_setor SERIAL PRIMARY KEY,
    nome_setor VARCHAR(100) NOT NULL UNIQUE
);

-- Tabela de Colaboradores
CREATE TABLE colaborador (
    id_colaborador SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email_celular VARCHAR(100) UNIQUE NOT NULL,
    cargo VARCHAR(50),
    id_adm INT,
    id_setor INT NOT NULL,
    CONSTRAINT colaborador_adm_fk FOREIGN KEY (id_adm) REFERENCES administrador_estoque (id_adm) ON DELETE SET NULL,
    CONSTRAINT colaborador_setor_fk FOREIGN KEY (id_setor) REFERENCES setor (id_setor) ON DELETE CASCADE
);

-- Tabela de Produtos (Otimizada para itens com e sem validade)
CREATE TABLE produto (
    id_produto SERIAL PRIMARY KEY,
    codigo_barra VARCHAR(50) UNIQUE NOT NULL,
    nome_produto VARCHAR(100) NOT NULL,
    validade DATE, -- REMOVIDO 'NOT NULL': Agora aceita itens como vassouras
    qtd_estoque INT NOT NULL DEFAULT 0 CHECK (qtd_estoque >= 0), -- Impede estoque negativo
    preco NUMERIC(10,2) NOT NULL CHECK (preco > 0), -- Impede preço zero ou negativo
    lote VARCHAR(50) DEFAULT 'N/A', -- Valor padrão caso não tenha lote
    id_setor INT,
    id_adm INT,
    CONSTRAINT produto_adm_fk FOREIGN KEY (id_adm) REFERENCES administrador_estoque (id_adm) ON DELETE SET NULL,
    CONSTRAINT produto_setor_fk FOREIGN KEY (id_setor) REFERENCES setor (id_setor) ON DELETE SET NULL
);

-- Tabela de Notificações
CREATE TABLE notificacao (
    id_notificacao SERIAL PRIMARY KEY,
    id_produto INT,
    id_colaborador INT,
    tipo_notificacao VARCHAR(50),
    mensagem TEXT,
    data_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_produto FOREIGN KEY (id_produto) REFERENCES produto (id_produto) ON DELETE CASCADE,
    CONSTRAINT fk_colaborador FOREIGN KEY (id_colaborador) REFERENCES colaborador (id_colaborador) ON DELETE SET NULL
);

-- Índices para Performance (Cruciais para o DatabaseManager e Modo TV)
CREATE INDEX idx_produto_validade ON produto (validade) WHERE validade IS NOT NULL;
CREATE INDEX idx_produto_codigo ON produto (codigo_barra);
CREATE INDEX idx_notificacao_data ON notificacao (data_envio DESC);

-- Carga Inicial de Teste
INSERT INTO administrador_estoque (nome, email, senha) VALUES 
('Rafael Barbosa', 'rafaelvbarbosa@gmail.com', '1234'),
('Marcos Almeida', 'marcos@gmail.com', '1234');

INSERT INTO setor (nome_setor) VALUES ('Limpeza'), ('Higiene'), ('Alimentos');